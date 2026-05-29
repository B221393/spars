% 動画内の点の軌跡トラッキングと描画
% タイトル: 動画内の点の軌跡トラッキングと描画
% 日付: 2026-05-19
% カテゴリ: プログラム

% 動画オブジェクトの作成
videoFileName = '99920250703172334.avi';
% 動画ファイルがパスにない場合は、フルパスを指定するかカレントディレクトリを移動してください
if ~exist(videoFileName, 'file')
    videoFileName = fullfile('C:\Users\yu_ci\desktop\kennkyuu', videoFileName);
end
videoObj = VideoReader(videoFileName);

% 軌跡データを保存するセル配列
% 各要素には、各フレームの [X座標, Y座標] の配列を格納します
trajectories = {}; 
frameCount = 1;

% 前フレームの重心座標を保持する変数
prevCentroids = [];

% 最初のフレームを描画用の背景として保存
backgroundFrame = [];

figure;
hold on;

while hasFrame(videoObj)
    frameRGB = readFrame(videoObj);
    frameGray = rgb2gray(frameRGB);
    
    if frameCount == 1
        backgroundFrame = frameRGB;
        imshow(backgroundFrame); hold on;
    end
    
    % 二値化と反転
    level = graythresh(frameGray);
    frameBW = ~imbinarize(frameGray, level);
    
    % 重心の抽出（ノイズ除去のため、面積が小さすぎるものは除外する設定を追加）
    stats = regionprops(frameBW, 'Centroid', 'Area');
    % 面積が10ピクセル以上のものを有効なドットとみなす（適宜調整）
    validStats = stats([stats.Area] > 10);
    
    % 現在のフレームの重心座標を取得 (N x 2 行列)
    currCentroids = cat(1, validStats.Centroid);
    
    if isempty(currCentroids)
        continue;
    end
    
    if frameCount == 1
        % 1フレーム目はそのまま保存
        trajectories{frameCount} = currCentroids;
        prevCentroids = currCentroids;
    else
        % --- ユーザーのアイデア「一番近いものを探す」部分 ---
        % 前フレームの点と現在フレームの点の距離をすべて計算
        distances = pdist2(prevCentroids, currCentroids);
        
        % matchpairsを使用して、距離の合計が最小になるように点を紐付ける
        % costUnmatched は紐付けられなかった場合のペナルティ値（距離のしきい値）
        costUnmatched = 50; 
        assignment = matchpairs(distances, costUnmatched);
        
        % 紐付けられた現在の点の座標を、前フレームと同じインデックス順に並べ替えて保存
        % これにより、trajectoriesの各行が同じ点の軌跡になります
        numPrevPoints = size(prevCentroids, 1);
        matchedCurrCentroids = NaN(numPrevPoints, 2); % 見失った点にはNaNを入れる
        
        for i = 1:size(assignment, 1)
            prevIdx = assignment(i, 1);
            currIdx = assignment(i, 2);
            matchedCurrCentroids(prevIdx, :) = currCentroids(currIdx, :);
        end
        
        trajectories{frameCount} = matchedCurrCentroids;
        
        % 次のフレームのために変数を更新 (NaNを補間するか、見失ったままにするかなどの処理が必要ですが、ここでは単純化のため見失った点は前回の位置とします)
        % 次回の基準とするため、現在の位置で上書き（NaNの場合は前回の位置を保持）
        nextCentroids = prevCentroids; 
        for i = 1:size(assignment, 1)
             nextCentroids(assignment(i, 1), :) = currCentroids(assignment(i, 2), :);
        end
        prevCentroids = nextCentroids;
    end
    
    frameCount = frameCount + 1;
end

% --- 軌跡の描画 ---
% trajectoriesセル配列から、各点（行）ごとに座標を取り出して線を描画
numPoints = size(trajectories{1}, 1);
numFrames = length(trajectories);

% 色をランダムに生成（点の区別を見やすくするため）
colors = lines(numPoints);

for ptIdx = 1:numPoints
    x_coords = zeros(1, numFrames);
    y_coords = zeros(1, numFrames);
    
    for fIdx = 1:numFrames
        if ~isempty(trajectories{fIdx}) && size(trajectories{fIdx}, 1) >= ptIdx
            x_coords(fIdx) = trajectories{fIdx}(ptIdx, 1);
            y_coords(fIdx) = trajectories{fIdx}(ptIdx, 2);
        else
            x_coords(fIdx) = NaN;
            y_coords(fIdx) = NaN;
        end
    end
    
    % NaNを取り除いて描画（線が途切れないようにする）
    validIdx = ~isnan(x_coords);
    plot(x_coords(validIdx), y_coords(validIdx), 'Color', colors(ptIdx, :), 'LineWidth', 1.5);
end

title('ドットの軌跡');
hold off;
disp('軌跡の描画が完了しました。');
