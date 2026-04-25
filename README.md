# text-of-joker-simulator

`A.C.T.I.S.` (Automated Card-battle Test and Interactive Simulation) の試作実装です。

メインプログラムが 2 つのプレイヤープログラムを子プロセスとして起動し、`stdio` 上の JSON Lines で対戦を進行します。

## 現在できること

- カードプール Excel (`text-of-joker.cardpool.xlsx`) の読込
- レギュレーション JSON の読込
- デッキ提出とデッキ検証
- 初期手札配布とマリガン
- `stdio` ベースの bot 対戦
- `state_update` / `request_action` / `choice_request` の往復
- 次の基本アクション
  - `set_trigger`
  - `drive`
  - `overdrive`
  - `override`
  - `retreat`
  - `attack`
  - `end_turn`
- ブロック
- 多段インターセプト
- トリガー左から順の解決
- 山札再構築ルール
- LIFE 0 以下での即終了
- ROUND 上限到達時の LIFE 比較決着
- キーワード能力の一部
  - `スピードムーブ`
  - `不屈`
  - `貫通`
- 人間向けの観戦ログ出力
  - `rendered_messages`
  - `[Rxx][Exxx][P?][REQ/RES/EVT] ...`

## 実行

```powershell
python -m unittest discover -s tests -v
```

```powershell
python -m tojs.bot --deck configs/decks/example_deck.json
```

```powershell
python -m tojs.demo_match --deck1 configs/decks/rg_beatdown.json --deck2 configs/decks/rg_beatdown.json --cycles 10 --seed 7
```

`demo_match` の出力 JSON には次が入ります。

- `snapshots`: サイクルごとの簡易状態
- `messages`: 生の通信ログ
- `rendered_messages`: 日本語寄りの整形ログ

## 主なファイル

- `configs/regulation.default.json`: 既定レギュレーション
- `configs/decks/example_deck.json`: 最小サンプルデッキ
- `configs/decks/rg_beatdown.json`: 進化入りの確認用デッキ
- `docs/architecture.md`: 構成と責務
- `docs/protocol.md`: `stdio` 通信仕様
- `docs/ability-system.md`: 誘発処理の方針
- `docs/rg_beatdown_support.md`: `rg_beatdown.json` の対応状況
- `src/tojs/game.py`: ゲーム状態とルール処理
- `src/tojs/match.py`: 子プロセスとの対戦進行
- `src/tojs/bot.py`: Python 製サンプル bot
- `src/tojs/demo_match.py`: ローカル対戦デモ

## 現在の未実装・簡略実装

- カードプール全体の個別効果
- 消滅ルールの完全実装
- 対象耐性系キーワード能力
- Docker 起動ラッパー本体
- GUI

## 開発方針

- まず JSON Lines の通信を堅くする
- 盤面ルールを小さく積み上げる
- 能力はイベント駆動で足す
- 追加実装ごとに `unittest` を増やす
