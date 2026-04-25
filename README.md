# text-of-joker-simulator

`A.C.T.I.S.` (Automated Card-battle Test and Interactive Simulation) の初期実装です。

現時点では、次の土台を用意しています。

- カードプール Excel (`.xlsx`) の読込
- レギュレーション設定ファイルの読込
- デッキ構成チェック
- `stdio` ベースの JSON Lines 通信フォーマット
- Python 製プレイヤー bot のひな形
- 初期手札配布、マリガン、ターン開始、`end_turn` までの最小進行
- `set_trigger` と同属性ユニットのコスト 1 軽減
- ログ表示向けイベント行フォーマットの提案実装
- TDD を進めるための `unittest` テスト群

## セットアップ

```powershell
python -m unittest discover -s tests -v
```

```powershell
python -m tojs.bot --deck configs/decks/example_deck.json
```

```powershell
python -m tojs.demo_match --cycles 2 --seed 7
```

`demo_match` の出力 JSON には、生の `messages` に加えて、日本語表示を含む `rendered_messages` も入ります。

## 主要ファイル

- `configs/regulation.default.json`: レギュレーションのひな形
- `docs/architecture.md`: 構成とセキュリティ方針
- `docs/protocol.md`: `stdio` プロトコル案とログ案
- `src/tojs/cardpool.py`: Excel からカードプールを読む
- `src/tojs/deck.py`: デッキ検証
- `src/tojs/regulation.py`: レギュレーション読込
- `src/tojs/protocol.py`: プレイヤー通信メッセージ
- `src/tojs/bot.py`: Python bot ひな形
- `src/tojs/game.py`: ゲーム状態と基本ターン進行
- `src/tojs/match.py`: bot 2 体を相手にした起動シーケンス
- `src/tojs/demo_match.py`: bot 同士のローカル実行デモ
- `src/tojs/cli.py`: メインプログラム入口
- `configs/decks/example_deck.json`: bot 用サンプルデッキ

## いま未実装の主な部分

- 戦闘処理を含む完全なゲームエンジン
- 全カード能力の解釈と解決
- Docker 実行ラッパー

ただし、後から拡張しやすいように、能力は JSON のまま構造化して保持する形にしてあります。

## 現在の進行範囲

- 両プレイヤーの `hello`
- デッキ提出と検証
- 初期手札 4 枚配布
- マリガン確認
- 先攻 1 ターン目開始
- `state_update` 配信
- `set_trigger`
- 同属性 trigger_zone カードによる `drive` コスト軽減
- `request_action` に対する `end_turn`

すでに `drive`、`attack`、`block` は最小実装済みです。
まだ `進化`、`trigger card 固有発火`、`intercept`、`能力解決` は未実装です。

## 挙動確認コマンド

レギュレーションを読み込み、サンプル bot 2 体で最小進行を確認できます。

```powershell
python -m tojs.demo_match --cycles 2 --seed 7
```

`boot` 時点では先攻手札 4 枚のまま、後攻へターンが移ると後攻手札が 6 枚になるはずです。
行動が進むと `battlefield_count` と `trigger_zone_count` の増減で、召喚やセットの動きも追えます。
