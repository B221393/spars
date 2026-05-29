% 1. 動画読み込み（fullfileを使用）とフォルダ準備
videoFolder = 'video'; % 動画が置いてあるフォルダ（環境に合わせて変更してください）
videoName = '99920250703172334.avi';
videoFileName = fullfile(videoFolder, videoName); 
videoObj = VideoReader(videoFileName);

outputFolder = 'video';
if ~exist(outputFolder, 'dir'), mkdir(outputFolder); end

% 2. トラッキング用変数の初期化（最小構成）
histories = {}; % 各ドットの軌跡(X,Y)を保持するセル配列
nextID = 1;
frameCount = 1;
csvData = {};

figure('Name', 'Minimal Dot Tracking');

while hasFrame(videoObj)
    frameRGB = readFrame(videoObj);
    frameGray = rgb2gray(frameRGB);
    
    % 3. 二値化処理と regionprops による特徴量抽出
    level = graythresh(frameGray);
    frameBW = ~imbinarize(frameGray, level);
    
    stats = regionprops(frameBW, 'Centroid', 'Area');
    
    % 面積から考えるのはノイズ除去（足切り）のみ。ブラーを考慮し700以上を抽出
    validStats = stats([stats.Area] > 700); 
    currPts = cat(1, validStats.Centroid);
    
    currIDs = NaN(size(currPts, 1), 1);
    
    % 4. 最も近い位置のドットを紐付ける（Nearest Neighbor）
    if frameCount > 1 && ~isempty(currPts)
        for id = 1:length(histories)
            if isempty(histories{id}), continue; end
            
            % 前のフレームの最終座標
            lastPos = histories{id}(end, :);
            
            % 現在のすべての点との直線距離を計算
            distances = sqrt(sum((currPts - lastPos).^2, 2));
            [minDist, minIdx] = min(distances);
            
            % 閾値（30px）以内で、まだ未割り当ての点なら同じドットとみなす
            if minDist < 30 && isnan(currIDs(minIdx))
                currIDs(minIdx) = id;
            end
        end
    end
    
    % 5. 履歴の更新（新規に点が生じるのを防ぎつつIDを管理）
    for i = 1:size(currPts, 1)
        % 紐付かなかった点にのみ、新しいIDを発行（基本は既存IDの維持）
        if isnan(currIDs(i))
            currIDs(i) = nextID;
            nextID = nextID + 1;
        end
        
        id = currIDs(i);
        if id > length(histories) || isempty(histories{id})
            histories{id} = currPts(i, :);
        else
            histories{id}(end+1, :) = currPts(i, :);
        end
        
        % CSV用データの蓄積
        csvData(end+1, :) = {frameCount, id, validStats(i).Area, currPts(i,1), currPts(i,2)}; %#ok<AGROW>
    end
    
    % 6. 描画と画像保存
    imshow(frameRGB); hold on;
    colors = lines(max(nextID, 10));
    for id = 1:length(histories)
        if ~isempty(histories{id})
            pts = histories{id};
            plot(pts(:,1), pts(:,2), '-', 'Color', colors(id,:), 'LineWidth', 1.5);
            plot(pts(end,1), pts(end,2), '.', 'Color', colors(id,:), 'MarkerSize', 10);
        end
    end
    title(sprintf('フレーム %d', frameCount));
    hold off; drawnow;
    
    imwrite(getframe(gca).cdata, fullfile(outputFolder, sprintf('frame_track_%04d.jpg', frameCount)));
    frameCount = frameCount + 1;
end

% 7. CSV保存
writetable(cell2table(csvData, 'VariableNames', {'Frame', 'DotID', 'Area', 'X', 'Y'}), 'trajectory_data_minimal.csv');
disp('処理が完了しました。');