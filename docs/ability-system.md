# Ability System

## Core Idea

能力処理はイベント駆動です。

1. 盤面で出来事が起こる
2. `AbilityEvent` を発行する
3. そのイベントに反応する能力を集める
4. FIFO で 1 つずつ解決する
5. 新しい出来事が出たらキューの後ろへ積む

この形にしている理由は、カードゲームで難しいのが「効果そのもの」よりも「いつ誘発して、どの順で解決するか」だからです。

## Current Events

現在使っている主なイベントは次のとおりです。

- `unit_entered`
- `unit_attacked`
- `player_attack_success`
- `unit_overclocked`
- `turn_end`

## Choice Model

プレイヤー選択は `choice_request` に統一しています。

現在の用途:

- 対象ユニット選択
- 手札コスト選択
- ブロック選択
- インターセプト選択

テストや簡易実行では、choice resolver が無い場合は先頭候補を自動選択します。

## Current Resolution Rules

- アタック宣言後、アタック時能力を先に解決します
- その後の盤面でブロック可否を判定します
- ブロッカーがいなければ `no_block` 扱いです
- ブロック成立時だけ intercept 選択に入ります
- intercept は攻撃側から開始し、双方が連続でパスするまで交互です
- trigger card は左から順に評価します
- 効果が何も及ばない trigger は場に残します

## Current Implemented Effect Shapes

- 登場時ダメージ
- 登場時ドロー
- 登場時 BP 減少
- アタック時 BP 増加
- アタック時ダメージ
- 手札コスト支払い後の BP 増加
- プレイヤーアタック成功時の trigger 破壊
- overclock 時の追加効果
- turn_end 時の行動権回復
- intercept による一時 BP 補正

## Current Keyword Support

- `スピードムーブ`
  - `drive` したターンでも `attack_restricted` を受けません
- `不屈`
  - `turn_end` 時に `exhausted = False`
- `貫通`
  - ブロックされた戦闘で攻撃ユニットが勝利した時だけ、相手ライフに 1 ダメージ

## Practical Extension Strategy

新しいカードや能力を足すときは、次の順で進めると壊れにくいです。

1. どのイベントで誘発するか決める
2. 選択が必要か決める
3. 盤面変化を小さく実装する
4. タイミング込みの回帰テストを追加する

## Current Limitation

- まだカードプール全体を網羅していません
- 汎用 DSL ではなく、個別能力と一部キーワード能力の混成です
- 対象耐性や消滅などの上位ルールは未実装または簡略実装です
