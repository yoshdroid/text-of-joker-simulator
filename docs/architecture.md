# Architecture

## Overview

- `main` 側がゲーム状態を持ちます
- `player` 側は状態通知を受けて応答を返します
- 通信は `stdin/stdout` の JSON Lines です
- 人間向けログは `demo_match` が整形します

## Directory Layout

- `src/tojs/`
  - コア実装
- `tests/`
  - `unittest`
- `configs/`
  - レギュレーションとデッキ
- `docs/`
  - 設計メモ

## Responsibility Split

- `cardpool.py`
  - Excel からカードプール読込
- `regulation.py`
  - レギュレーション読込
- `deck.py`
  - デッキ検証
- `protocol.py`
  - メッセージ構造とログ整形
- `game.py`
  - 盤面状態、合法手、戦闘、能力解決
- `match.py`
  - bot 2 体との通信シーケンス
- `bot.py`
  - Python 製サンプル bot
- `demo_match.py`
  - ローカル観戦用の実行入口

## Ability Data Policy

カードプールの `abilities` はそのまま保持します。
ただし、すべてを汎用解釈するのではなく、当面は次の 2 系統で扱っています。

- 個別カード効果
- キーワード能力

現在のキーワード能力実装は `スピードムーブ`、`不屈`、`貫通` です。

## Match Flow

1. カードプール読込
2. レギュレーション読込
3. 先攻 / 後攻 bot 起動
4. デッキ提出と検証
5. 初期手札配布
6. マリガン
7. 先攻ターン開始
8. `state_update` 配信
9. `request_action` / `choice_request` に従って進行
10. 決着時に終了

## Logging

内部の機械向け通信は JSON を維持します。
観戦用には `rendered_messages` を別途生成します。

現在の表示例:

```text
[R04][E003][P1][REQ] request_action actions=drive,attack,end_turn
[R04][E004][P1][RES] action attack attacker_index=0
```

## Security Direction

現時点ではローカル子プロセス起動を使っています。
将来的な隔離候補は次のとおりです。

- Docker Desktop
- Windows Job Object
- 低権限ユーザー実行
- timeout / resource 制限
