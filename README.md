# FILLIN デザイン制作ツール

FILLINの商品画像加工など、制作に使うスクリプトと日本語の運用資料を管理します。

## 白背景画像

元画像をトーンカーブで白くした下地に、元画素の切り抜き商品を重ねます。下地に商品の形と影を残し、切り抜き不足を補完します。

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/product_white_background.py /path/to/source.jpg \
  --output-dir output/model-color --knee 160 --white-point 235
```

[処理方法・調整・確認項目](docs/white-background.md)

マスクがある場合は `--mask /path/to/mask.png` を指定します。ない場合はU2NetPモデルを初回ダウンロードします。商品の写真・フォント・モデル本体・認証情報はこのリポジトリに含めません。

完成画像、下地、商品レイヤー、マスク、処理設定を出力します。背景が残る場合はwhite-pointを下げ、影が消える場合は上げて原寸比較してください。商品や撮影条件によって調整が必要です。

## 追加・更新のルール

- スクリプトは `scripts/`、日本語の説明は `docs/` に置きます。
- 入出力、依存、実行例、確認方法を説明に記載します。
- 商品の原本を上書きせず、出力先を分けます。
- 数値や処理方式を変更したら、検証結果と更新理由を記録します。

## 更新履歴

- 2026-10-14：白背景画像作成CLIとU2NetP切り抜きワーカーを登録。CLASSIC WHITEで不透明商品画素の保持と四隅の純白を確認。
