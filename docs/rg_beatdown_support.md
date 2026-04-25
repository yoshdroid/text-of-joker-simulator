# RG Beatdown Support

`configs/decks/rg_beatdown.json` に入っているカードの、現在の実装対応状況を整理したメモです。

## Deck Summary

- 40 枚
- 赤緑中心
- 進化カードあり
- trigger / intercept を多く含む確認用デッキ

## Supported in Practice

次のカードは、個別能力または現在のキーワード能力まで含めて確認しやすいカードです。

- `1-0-002`
  - アタック時 BP +2000
- `1-0-004`
  - アタック時 1000 ダメージ
- `1-0-007`
  - overclock 時ライフ -1
- `1-0-010`
  - 手札 1 枚 discard 後に BP +4000
  - プレイヤーアタック成功時に相手 trigger を最大 2 枚破壊
- `1-0-012`
  - 登場時 4000 ダメージ
  - アタック成功時の trigger 破壊
- `1-0-040`
  - 登場時ドロー
- `1-0-051`
  - 登場時 敵 BP -4000
- `1-0-057`
  - trigger から trigger サーチ
- `1-0-061`
  - trigger から intercept サーチ
- `1-0-062`
  - trigger から 1 ドロー
- `1-0-065`
  - intercept: 相手ユニット BP -2000
- `1-0-074`
  - intercept: 自ユニット BP +2000
- `1-0-081`
  - intercept: 攻撃ユニット BP +3000
- `1-0-096`
  - intercept: 自ユニット BP +3000

## Supported by Keyword

次のカードは、個別カード番号ではなくキーワード能力として効く状態です。

- `1-0-044`
  - `不屈`
- `1-0-048`
  - `不屈`
- `1-0-046`
  - `貫通`
- `1-0-052`
  - `貫通`
  - `不屈`
- `1-0-006`
  - `スピードムーブ`
- `1-0-021`
  - `不屈`

## Supported Core Rules Around This Deck

- `set_trigger`
- `drive`
- `overdrive`
- `override`
- `retreat`
- `attack`
- `block`
- 多段 intercept
- trigger 左から順解決
- unit / evolution によるコスト軽減
- 戦闘勝利時の clock up
- overclock
- LIFE 0 即終了
- ROUND 上限決着

## Still Missing

- 一部カードの固有能力
- ability JSON を汎用 DSL として解釈する仕組み
- 消滅ルールの完全実装
- 対象耐性系のキーワード能力

## Practical Note

`rg_beatdown.json` は、今のエンジンで

- 進化
- trigger / intercept
- 戦闘
- 一部キーワード能力

をまとめて確認するのに向いています。
