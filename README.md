# 🚀 GENRE-FOLDERS: Multi-Task AI Repository

## 概要
このプロジェクトは、AIエージェントによる多角的タスク（将棋、音声、研究、試験対策）の自動化と自律進化を目的としています。
すべてのドキュメントとコード生成は、ローカルLLM（Ollama）によって管理されています。

---

## 📂 フォルダ構成

### ♟️ [SHOGI](./SHOGI)
- **JOSEKI_ANALYZER.py**: ネット検索とローカルLLMを組み合わせた定跡弱点解析システム。
- 2026年最新のAIトレンド（エルモ囲い急戦等）を反映した詳細レポートを自動生成。

### 🎙️ [VOICE](./VOICE)
- **INTEGRATED_AGENT.py**: OpenCV（視覚）とローカルLLM（脳）を統合した対話エージェントの雛形。
- 2026年標準の超低遅延ノイズ除去（DeepFilterNet3）構成案。

### 🔬 [RESEARCH](./RESEARCH)
- **PRO_TRAJECTORY_TRACKER.py (V4)**: カルマンフィルタ（Kalman Filter）を搭載。
- 一時的な遮蔽（オクルージョン）や重なりが発生しても、物理法則に基づき座標を推定し、軌跡を維持します。

### 💻 [DEVELOPMENT](./DEVELOPMENT)
- 自律改善ループ（Codex vs Local Agent）のベンチマークと最適化。
- Canvas API等を用いたフロントエンドパフォーマンス向上。

---

## 🛠️ 使い方

1. **環境構築**
   - Python 3.11+, Node.js 20+
   - Ollama (Local LLM Server) が起動していること。
   ```bash
   pip install opencv-python scipy matplotlib requests
   ```

2. **実行**
   - 各フォルダ内のスクリプトを個別に実行、または `codex-vs-local-agent-loop` 内のバッチファイルを使用。

---

## 📄 ライセンス
MIT License
