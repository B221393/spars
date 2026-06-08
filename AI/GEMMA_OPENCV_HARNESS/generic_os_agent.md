# 汎用OSエージェントへの進化：Slay the Spire 2の自動化ロジックの応用とプロンプト設計
2026-06-08

Slay the Spire 2 (StS2) で構築した「状態認識 → LLM推論 → アクション実行 → エラー評価 (自己修復)」のクローズドループ・アーキテクチャを、一般的なデスクトップ操作自動化 (RPA / OS Agent) へ拡張するためのアドバイスとプロンプト設計案です。

---

## 1. Slay the Spire 2 から汎用作業への応用アドバイス

StS2の自動化で得られた知見は、以下のステップを通じて汎用的なOS操作エージェントへとスムーズに拡張可能です。

* **状態取得 (State Acquisition) の切り替え:**
  StS2ではMod APIポート (15526) から完全なJSONデータを取得可能でしたが、汎用OS環境 (ブラウザやエクスプローラ等) ではAPIが用意されていません。
  これに対しては、OpenCVによる画面スクリーンショット内のテンプレートマッチング (特定のボタンやアイコンの座標特定) を行うか、あるいはVision-LLM (マルチモーダルモデル) を用いて画面全体を直接解釈させるアプローチに切り替えます。
* **マウス操作・キャリブレーションデータの流用:**
  StS2用に収集・算出した「クリック座標の分散や誤差修正ロジック (click_calibration_data.json)」は、PyAutoGUI等のGUI操作モジュールと統合することで、そのまま「人間らしい自然でランダム性を含んだマウス移動・クリック操作」に流用できます。
* **AIモデルのスケールアップ:**
  ゲームのような閉じたルールであれば軽量モデル (Gemma 2 2Bクラス) で十分ですが、多種多様なウィンドウやフォルダが混在するデスクトップ環境の文脈を正しく理解するためには、Gemma 2 (9B / 27B) やその他の大規模モデルへスケールアップすることで、抽象的な指示から具体的座標やステップへの分解精度が劇的に向上します。

---

## 2. 汎用デスクトップ操作用エージェントのプロンプト定義

### 基本設定
* **AIモデル:** ローカル大規模言語モデル (Gemma-2-9b-it等) または Vision対応マルチモーダルモデル
* **システムプロンプト (System Prompt):**

```text
あなたはユーザーのデスクトップ環境で自律的に作業を行う汎用OSエージェントです。
現在画面上の認識可能なUI要素と、過去の操作履歴（error_history）がJSON形式で与えられます。

【制約事項】
1. 目的を達成するために、次に取るべき「単一のステップ」を推論してください。
2. 過去のステップで変化がない（stuck_counterが増加している）場合は、別のアプローチ（スクロールする、Escキーを押す等）を選択して無限ループを回避してください。
3. 出力は必ず以下のJSONスキーマに従うこと。

【出力スキーマ】
{
  "thought_process": "現在の画面状態と目標を比較し、なぜ次のアクションを選ぶのかの論理的推論",
  "action_type": "CLICK | TYPE | SCROLL | WAIT | DONE",
  "target_coordinate": {"x": 整数, "y": 整数},
  "input_text": "TYPEの場合のみ入力",
  "confidence": 0.0から1.0の値
}
```

---

### プロンプト入力例 (User Input Example)

```json
{
  "target_objective": "指定されたフォルダ内のCSVファイルを読み込み、経費の合計値を計算して新しいテキストファイルに保存せよ。",
  "current_screen_state": {
    "focus": "Desktop",
    "detected_elements": [
      {"id": 1, "type": "folder", "name": "経費データ", "x": 150, "y": 200},
      {"id": 2, "type": "icon", "name": "Chrome", "x": 50, "y": 200}
    ]
  },
  "error_history": []
}
```

---

### 出力例 (Expected Agent Response)

```json
{
  "thought_process": "現在の目標はCSVファイルを読み込むことである。画面上には目的のファイルが入っていると思われる'経費データ'フォルダが存在する。まずはこのフォルダを開くために、ダブルクリックに相当するCLICKアクションをフォルダの座標(150, 200)に対して実行する。",
  "action_type": "CLICK",
  "target_coordinate": {"x": 150, "y": 200},
  "input_text": "",
  "confidence": 0.95
}
```

---

## 3. 実行およびクローズドループ・評価の設計

1. **パースとキャリブレーション:**
   エージェントが生成したJSONからアクションを取り出し、キャリブレーション済みのマウス操作・入力処理関数に渡してOS上でクリック・キー入力を実行。
2. **待機と再検証:**
   実行完了後、画面遷移や結果反映を待つために適切な待機時間 (WAIT) を挟み、再度スクリーンショット等から状態を取得。
3. **エラーハンドリング (自己修復):**
   画面が遷移しなかった場合やエラー画面が表示された場合は、stuck_counter を増やして `error_history` を更新し、LLMに別ルートを再考させる。

---

## 4. 視覚的記憶（Template Matching）とOCRを組み合わせた進化版プロンプト設計

より高度な自律動作のため、絶対座標指定ではなく「事前に切り抜いたUI画像のキー名（visual_memories）」および「OCR検出テキスト（ocr_detected_text）」をベースにした進化版のプロンプト構成です。これにより画面解像度やウィンドウ配置の変更に極めて強い設計となります。

### システムプロンプト（進化版）

```text
あなたはユーザーのPC環境に常駐し、タスクを完全自律で完遂するOS統合型エージェントです。ユーザーからの手動介入（助け）は一切ありません。行き詰まった場合は、画面内の情報から別の経路を深く推論し、自己解決してください。

あなたは「視覚的記憶（事前に切り抜かれたUI画像のリスト）」を持っています。画面上の絶対座標ではなく、この「視覚的記憶のキー（名前）」を指定することで、システムがOpenCVを用いて画面内を検索し、正確な位置をクリックします。

【制約事項】
1. 現在の「タスク脳（Brain）」の目標を達成するための次の一手を論理的に推論すること。
2. クリック操作は、可能な限り「visual_memories」に登録されているキー名を使用すること（例：検索ボックス、送信ボタン等）。
3. 過去のアクション（recent_actions）で失敗が続いている場合、同じ操作を繰り返さず、スクロールや別のボタンの探索など代替手段を実行すること。
4. 出力は必ず以下のJSONスキーマに従うこと。

【出力JSONスキーマ】
{
  "deep_reasoning": "現在の画面状況（OCR情報）と過去の履歴を分析し、目標達成のために何がボトルネックになっているか、次にどうすべきかの深い思考",
  "action_type": "MATCH_CLICK | OCR_CLICK | TYPE | SCROLL | WAIT | COMPLETE",
  "target_identifier": "MATCH_CLICKの場合はvisual_memoriesのキー名。OCR_CLICKの場合は画面上のテキスト",
  "input_text": "TYPEの場合のみ、入力する文字列",
  "confidence_score": 0.0から1.0
}
```

---

### 入力と評価/結果のサイクル例

* **入力:**
  ```json
  {
    "current_brain": "リサーチタスク脳",
    "current_goal": "最新のAIモデルの論文を検索し、PDFをダウンロードする",
    "screen_state": {
      "active_window": "Google Chrome",
      "ocr_detected_text": ["Google", "検索", "I'm Feeling Lucky", "Gmail", "画像"]
    },
    "visual_memories": [
      "google_search_box_empty",
      "google_search_box_active",
      "google_search_button",
      "download_icon_arrow"
    ],
    "recent_actions": [
      {"action": "MATCH_CLICK", "target": "chrome_icon", "status": "success"},
      {"action": "WAIT", "target": "none", "status": "success"}
    ]
  }
  ```

* **出力:**
  ```json
  {
    "deep_reasoning": "現在の目標は最新のAIモデルの論文を検索し、PDFをダウンロードすることです。現在、Google Chromeがアクティブであり、Googleのホームページ（検索ボックスが空で未フォーカスの状態）が表示されているとOCRおよび画面状態から判断できます。検索用キーワードを入力するためには、まず検索窓をフォーカスしてアクティブにする必要があります。したがって、visual_memories内にある空の検索ボックスを示すテンプレート画像キー 'google_search_box_empty' をMATCH_CLICKによって選択し、クリック操作を実行して入力準備を整えます。",
    "action_type": "MATCH_CLICK",
    "target_identifier": "google_search_box_empty",
    "input_text": "",
    "confidence_score": 0.98
  }
  ```

* **評価/結果の仕組み:**
  1. システム側（Python/OpenCV）がエージェントの出力したJSONをパースする。
  2. `MATCH_CLICK` と判定されたため、`visual_memories` 内の `"google_search_box_empty"` に紐づく基準画像ファイルを使用して `cv2.matchTemplate` (テンプレートマッチング) を実行。
  3. スクリーンショット内から一致する部分を特定し、その座標にマウスを移動してクリックを実行。
  4. その後、次の画面状態（テキストボックスにフォーカスが当たり、アクティブになった状態）のOCRテキストとスクリーンショットを取得し、再度エージェントへ入力してループを継続。

