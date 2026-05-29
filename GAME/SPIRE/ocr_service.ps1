# Set console encoding to UTF-8 to prevent character encoding issues
[System.Console]::InputEncoding = [System.Text.Encoding]::UTF8
[System.Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Load required assemblies once
[System.Reflection.Assembly]::Load("System.Runtime.WindowsRuntime, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089") | Out-Null
[void][Windows.Media.Ocr.OcrEngine, Windows.Media, ContentType=WindowsRuntime]
[void][Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType=WindowsRuntime]
[void][Windows.Storage.Streams.IRandomAccessStream, Windows.Storage, ContentType=WindowsRuntime]
[void][Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics, ContentType=WindowsRuntime]
[void][Windows.Media.Ocr.OcrResult, Windows.Media, ContentType=WindowsRuntime]

$asTaskMethods = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { 
    $_.Name -eq 'AsTask' -and 
    $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name.StartsWith('IAsyncOperation`1')
}
$asTaskMethod = $asTaskMethods[0]

function Get-AsyncResult($asyncOp, $resultType) {
    $genericMethod = $global:asTaskMethod.MakeGenericMethod($resultType)
    $task = $genericMethod.Invoke($null, @($asyncOp))
    return $task.Result
}

# OCR engine instance created once
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()

[System.Console]::WriteLine("READY")

while ($true) {
    $line = [System.Console]::ReadLine()
    if ($null -eq $line -or $line -eq "EXIT") {
        break
    }
    
    $filePath = $line.Trim()
    if (Test-Path $filePath) {
        $dotNetStream = $null
        try {
            # Retry mechanism to handle transient file locks
            $attempts = 0
            while ($attempts -lt 5 -and $null -eq $dotNetStream) {
                try {
                    $dotNetStream = [System.IO.File]::OpenRead($filePath)
                } catch {
                    $attempts++
                    [System.Threading.Thread]::Sleep(10)
                }
            }
            
            if ($null -eq $dotNetStream) {
                throw "File access timeout: $filePath is locked by another process."
            }

            $stream = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($dotNetStream)
            
            $asyncOp3 = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
            $decoder = Get-AsyncResult $asyncOp3 ([Windows.Graphics.Imaging.BitmapDecoder])
            
            $asyncOp4 = $decoder.GetSoftwareBitmapAsync()
            $bitmap = Get-AsyncResult $asyncOp4 ([Windows.Graphics.Imaging.SoftwareBitmap])
            
            if ($engine -ne $null) {
                $asyncOp5 = $engine.RecognizeAsync($bitmap)
                $result = Get-AsyncResult $asyncOp5 ([Windows.Media.Ocr.OcrResult])
                
                $output = @()
                foreach ($l in $result.Lines) {
                    foreach ($word in $l.Words) {
                        $rect = $word.BoundingRect
                        $output += [PSCustomObject]@{
                            text = $word.Text
                            x = [int]$rect.X
                            y = [int]$rect.Y
                            w = [int]$rect.Width
                            h = [int]$rect.Height
                        }
                    }
                }
                
                # Convert output to JSON and then base64 encode it to prevent console encoding issues
                $json = $output | ConvertTo-Json -Compress
                $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
                $b64 = [System.Convert]::ToBase64String($bytes)
                [System.Console]::WriteLine("OK:" + $b64)
            } else {
                [System.Console]::WriteLine("ERROR:OcrEngine initialization failed")
            }
        } catch {
            $err = $_.Exception.Message.Replace("`r", "").Replace("`n", " ")
            $errBytes = [System.Text.Encoding]::UTF8.GetBytes($err)
            $errB64 = [System.Convert]::ToBase64String($errBytes)
            [System.Console]::WriteLine("ERROR:" + $errB64)
        } finally {
            if ($null -ne $dotNetStream) {
                $dotNetStream.Close()
            }
        }
    } else {
        [System.Console]::WriteLine("ERROR:FileNotFound")
    }
}
