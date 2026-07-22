# Ke hoach nang cap AI local-first cho web_trash_sorting

## 1. Muc tieu

Muc tieu hien tai la uu tien he thong chay on dinh tren may local:

- Train model phan loai rac co do chinh xac tot hon model cu.
- Backend Python (`api_server.py`) nhan dien bang model `.h5` moi.
- Frontend uu tien Python API khi chay local.
- Van chuan bi san duong convert sang TensorFlow.js de sau nay deploy Vercel, nhung khong coi Vercel la yeu cau ngay bay gio.

Luong mong muon:

```text
dataset/
  -> train_dl_model.py
  -> trash_classifier_model.h5
  -> api_server.py
  -> frontend camera recognition
```

Luong chuan bi cho sau nay:

```text
trash_classifier_model.h5
  -> SavedModel
  -> public/tfjs_model/
  -> frontend local TF.js model
  -> Vercel/static hosting
```

## 2. Nguyen tac thiet ke

### 2.1. Local-first

Trong giai do hien tai, Python API la che do nhan dien chinh vi:

- De debug hon.
- Dung truc tiep model `.h5` sau khi train.
- Khong can convert TF.js moi test duoc.
- Phu hop khi may local co san Python/TensorFlow.

Frontend nen uu tien:

```text
Python API local -> Local TF.js model -> Teachable Machine -> Gemini -> MobileNet fallback
```

### 2.2. Vercel-ready, nhung optional

Van giu:

- Thu muc `public/tfjs_model/`.
- Code frontend load local TF.js model.
- Script convert TF.js.

Nhung convert TF.js khong nen bat buoc moi lan train. Nen bien thanh buoc tuy chon.

## 3. Cac van de hien tai can sua

### 3.1. Training khong that su dang chay ngam

Hien tai khong co process `python`, `node`, hoac `npx` dang train/convert. File trong `public/tfjs_model/` la output cu.

Can tranh thong bao "training dang chay ngam" neu thuc te chua co process.

### 3.2. Model TF.js hien tai la LayersModel, khong phai GraphModel

Frontend dang dung:

```js
tf.loadGraphModel('/tfjs_model/model.json')
```

Nhung `public/tfjs_model/model.json` hien tai co:

```json
"format": "layers-model"
```

Neu dung model cu nay, frontend se load fail va fallback sang MobileNet.

Giai phap:

- Truoc mat local-first nen khong phu thuoc vao file TF.js.
- Khi can TF.js, convert lai dung dinh dang `tfjs_graph_model`.

### 3.3. Bug luu best model trong `train_dl_model.py`

Script hien tai co rui ro:

- Phase 1 co the tot hon fine-tune.
- Script co logic so sanh phase 1 voi fine-tune.
- Nhung cuoi script van `model.save(MODEL_H5)`, co the ghi de best model bang model fine-tune kem hon.

Can sua de chi luu model tot nhat that su.

### 3.4. Label mapping chua chac khop frontend

`src/mockData.js` co cac `id` nhu:

- `bottle`
- `soda_can`
- `newspaper`
- `glass_bottle`
- `plastic_bag`

Dataset folder co the la:

- `plastic_bottle`
- `plastic`
- `paper`
- `glass`
- `metal`

Neu model tra ve label khong khop `trashItems.id`, frontend co the khong tim thay item.

Can dung mapping dataset folder -> frontend item id mot cach nhat quan.

## 4. Ke hoach thuc hien chi tiet

## Buoc 1: Kiem ke dataset va frontend item ids

### Viec can lam

1. Doc danh sach folder trong `dataset/`.
2. Doc danh sach `id` trong `src/mockData.js`.
3. Tao bang mapping tu folder dataset sang frontend id.
4. Danh dau cac folder chua map duoc.
5. Danh dau cac frontend id chua co anh train.

### Output mong muon

Co mot mapping ro rang, vi du:

```python
FOLDER_TO_ID = {
    "plastic_bottle": "bottle",
    "plastic": "bottle",
    "paper": "newspaper",
    "newspaper": "newspaper",
    "cardboard": "cardboard",
    "glass": "glass_bottle",
    "glass_bottle": "glass_bottle",
    "metal": "soda_can",
    "tin_can": "soda_can",
    "soda_can": "soda_can",
    "plastic_bag": "plastic_bag",
    "battery": "battery",
}
```

### Tieu chi hoan thanh

- Khong co folder dataset quan trong nao bi bo qua ma khong co ly do.
- Tat ca label train sinh ra deu map duoc sang `trashItems.id`.

## Buoc 2: Sua `train_dl_model.py` de dung label mapping that su

### Viec can lam

Hien tai `ImageDataGenerator.flow_from_directory()` mac dinh coi moi folder la mot class rieng. Neu can gom nhieu folder ve cung mot frontend id, co hai cach:

### Cach A: Don gian, doi/merge folder dataset

Sap xep lai folder dataset sao cho moi folder trung voi frontend id.

Vi du:

```text
dataset/
  bottle/
  soda_can/
  newspaper/
  cardboard/
  glass_bottle/
  plastic_bag/
  battery/
```

Uu diem:

- De dung voi `flow_from_directory()`.
- It code phuc tap.

Nhuoc diem:

- Phai di chuyen/doi ten du lieu.

### Cach B: Viet custom dataframe generator

Tao danh sach file anh va label da map, sau do dung:

```python
ImageDataGenerator.flow_from_dataframe()
```

Uu diem:

- Khong can doi folder dataset.
- Linh hoat, nhieu folder co the cung mot label.

Nhuoc diem:

- Code phuc tap hon mot chut.

### Khuyen nghi

Dung **Cach B** de khong phai sua cau truc dataset hien tai.

### Tieu chi hoan thanh

- `class_labels` trong training la frontend ids, khong phai ten folder goc.
- `labels.json` sinh ra khop voi output classes cua model.

## Buoc 3: Sua logic checkpoint de khong mat best model

### Viec can lam

Sua luong train thanh:

```text
Train phase 1
  -> save best_phase1.h5
  -> record best_val_acc_p1

Fine-tune
  -> save best_finetune.h5
  -> record best_val_acc_ft

Compare
  -> choose winner checkpoint
  -> copy/load winner as trash_classifier_model.h5
```

Khong goi `model.save(MODEL_H5)` o cuoi neu model hien tai khong phai best.

### Tieu chi hoan thanh

- Neu fine-tune kem hon phase 1, file cuoi cung van la phase 1 best.
- Neu fine-tune tot hon, file cuoi cung la fine-tune best.

## Buoc 4: Giu EfficientNetB0 preprocessing nhat quan

### Viec can lam

Dam bao 3 noi khop nhau:

1. Training:

```python
ImageDataGenerator(...)
```

Khong dung:

```python
rescale=1./255
```

2. Backend:

```python
arr = np.array(img, dtype=np.float32)
```

Khong chia 255.

3. Frontend TF.js sau nay:

```js
tf.browser.fromPixels(canvas)
  .resizeBilinear([224, 224])
  .toFloat()
  .expandDims(0)
```

Khong `.div(255)`.

### Tieu chi hoan thanh

- Input train, backend predict, va frontend TF.js deu cung dai gia tri `0-255`.

## Buoc 5: Sua `api_server.py` cho che do local on dinh

### Viec can lam

1. Kiem tra ton tai:

- `trash_classifier_model.h5`
- `public/tfjs_model/labels.json` hoac file label rieng cho backend.

2. Neu thieu file, server bao loi ro rang.
3. Dam bao label tra ve la frontend item id.
4. Tra response de frontend dung truc tiep:

```json
{
  "class": "bottle",
  "confidence": 0.92,
  "emoji": "...",
  "name": "...",
  "category": "green"
}
```

5. Nen doi field `bin` thanh `category` cho khop `mockData.js`, hoac tra ca hai neu muon tuong thich nguoc.

### Tieu chi hoan thanh

- `GET /health` tra ve `status: ok`.
- `POST /predict` tra label khop voi frontend.
- Neu model/labels thieu, loi de hieu.

## Buoc 6: Sua frontend uu tien local Python API

### Viec can lam

Trong `src/main.js`, logic load AI nen la:

```text
Neu dang localhost:
  thu Python API truoc

Neu Python API fail:
  thu Local TF.js model neu co

Neu co Teachable Machine URL:
  thu Teachable Machine

Neu co Gemini key:
  dung Gemini

Cuoi cung:
  MobileNet fallback
```

Co the dinh nghia:

```js
const isLocalHost =
  location.hostname === 'localhost' ||
  location.hostname === '127.0.0.1';
```

### Trang thai UI mong muon

- Python API thanh cong:

```text
Python AI API
```

- Local TF.js thanh cong:

```text
Local AI
```

- Fallback:

```text
AI Mac dinh (MobileNet)
```

### Tieu chi hoan thanh

- Khi chay `api_server.py`, frontend dung Python API.
- Khi khong chay backend, frontend khong bi chet, van fallback duoc.

## Buoc 7: Bien convert TF.js thanh optional

### Viec can lam

Khong bat buoc convert moi lan train.

Lua chon de implement:

### Option A: CLI flag trong Python

```bash
python train_dl_model.py --convert-tfjs
```

Mac dinh:

```bash
python train_dl_model.py
```

chi train va luu `.h5`.

### Option B: Tach command convert

Them script npm:

```json
{
  "scripts": {
    "convert:tfjs": "tfjs-converter --input_format=tf_saved_model --output_format=tfjs_graph_model saved_model_tmp public/tfjs_model"
  }
}
```

Sau nay chay:

```bash
npm run convert:tfjs
```

### Khuyen nghi

Dung ca hai:

- Python co flag `--convert-tfjs`.
- `package.json` co script convert ro rang.

### Tieu chi hoan thanh

- Train local khong bi fail chi vi converter loi.
- Khi can Vercel, co command convert ro rang.

## Buoc 8: Pin dependency TF.js converter

### Viec can lam

Them dependency vao `package.json`, vi du:

```json
"devDependencies": {
  "@tensorflow/tfjs-converter": "...",
  "vite": "^5.2.11"
}
```

Can chon version tuong thich voi moi truong hien tai.

### Tieu chi hoan thanh

- Khong phu thuoc vao `npx` tai version ngau nhien.
- May khac clone project co the `npm install` roi convert.

## Buoc 9: Validate sau khi train/convert

### Validate model `.h5`

Can kiem tra:

- File `trash_classifier_model.h5` ton tai.
- Model load duoc.
- Output shape bang so labels.

### Validate labels

Can kiem tra:

- `labels.json` ton tai.
- So labels bang output classes.
- Moi label deu co item trong `src/mockData.js`.

### Validate TF.js neu convert

Can kiem tra:

- `public/tfjs_model/model.json` ton tai.
- Co file `group*-shard*.bin`.
- `model.json` la GraphModel neu frontend dung `tf.loadGraphModel`.

## Buoc 10: Test local

### 10.1. Build frontend

```bash
npm run build
```

Tieu chi:

- Build thanh cong.
- Khong loi import/module.

### 10.2. Chay backend

```bash
python api_server.py
```

Kiem tra:

```text
GET http://localhost:5000/health
```

Tieu chi:

- Server bao model loaded.
- So class khop labels.

### 10.3. Chay frontend

```bash
npm run dev
```

Tieu chi:

- Trang web mo duoc.
- Camera xin quyen va hien hinh.
- AI status hien `Python AI API`.
- Dua vat vao camera co du do tin cay.

### 10.4. Test cac vat de nhan

Nen test truoc:

- Chai nhua.
- Lon nuoc ngot.
- Giay/bao.
- Pin.
- Tui nilon.

Ghi lai:

```text
Vat test | Prediction | Confidence | Dung/Sai | Ghi chu anh sang/goc quay
```

## 5. Thu tu uu tien thuc hien

### Phase 1: Sua nen tang label va training

1. Kiem ke dataset va `mockData.js`.
2. Sua label mapping.
3. Sua checkpoint best model.
4. Dam bao preprocessing `0-255`.
5. Train lai model.

### Phase 2: Sua backend va frontend local

1. Sua `api_server.py` doc labels moi.
2. Sua response cho khop frontend.
3. Sua frontend uu tien Python API local.
4. Test `api_server.py` + `npm run dev`.

### Phase 3: Chuan bi Vercel sau nay

1. Tach convert TF.js thanh optional.
2. Pin `@tensorflow/tfjs-converter`.
3. Sua frontend load GraphModel chac hon.
4. Validate TF.js output.

## 6. Rủi ro va cach xu ly

### Rui ro 1: Dataset lech class

Neu class A co 1000 anh, class B co 20 anh, model de thien vi.

Cach xu ly:

- Can bang them anh.
- Dung class weighting.
- Giam so class trong giai do dau, chi train cac vat quan trong.

### Rui ro 2: Label khong khop frontend

Model tra `plastic_bottle`, frontend chi co `bottle`.

Cach xu ly:

- Bat buoc validate labels voi `trashItems.id`.
- Khong cho training/convert ket thuc thanh cong neu label khong map duoc.

### Rui ro 3: EfficientNetB0 nang cho trinh duyet

Khi sau nay chay TF.js tren browser, EfficientNetB0 co the cham tren may yeu.

Cach xu ly:

- Hien tai dung backend local nen khong gap nhieu.
- Sau nay neu deploy static, can test FPS.
- Co the giam tan suat predict loop.
- Can nhac MobileNetV3/EfficientNetLite neu can nhe hon.

### Rui ro 4: Convert TF.js loi version

TensorFlow/Keras va tfjs-converter co the khong tuong thich.

Cach xu ly:

- Pin dependency.
- Giu convert optional.
- Validate sau convert.

## 7. Checklist hoan thanh

### Bat buoc cho local

- [ ] Dataset folders duoc map sang frontend item ids.
- [ ] `train_dl_model.py` khong ghi de best model bang model kem hon.
- [ ] `trash_classifier_model.h5` la model tot nhat sau train.
- [ ] `labels.json` khop output shape cua model.
- [ ] Tat ca labels deu tim duoc trong `src/mockData.js`.
- [ ] `api_server.py` load model va labels thanh cong.
- [ ] `GET /health` thanh cong.
- [ ] Frontend dung Python API khi chay local.
- [ ] `npm run build` thanh cong.
- [ ] Camera test nhan dien duoc it nhat mot so vat chinh.

### Chuan bi cho Vercel sau nay

- [ ] Convert TF.js la optional.
- [ ] `@tensorflow/tfjs-converter` duoc pin trong `package.json`.
- [ ] `public/tfjs_model/model.json` la GraphModel khi dung `tf.loadGraphModel`.
- [ ] Frontend fallback duoc khi khong co Python API.
- [ ] README co huong dan convert/deploy sau nay.

## 8. Lenh du kien su dung

### Train local

```bash
python train_dl_model.py
```

### Chay backend

```bash
python api_server.py
```

### Chay frontend

```bash
npm run dev
```

### Build frontend

```bash
npm run build
```

### Convert TF.js sau nay

```bash
python train_dl_model.py --convert-tfjs
```

hoac:

```bash
npm run convert:tfjs
```

## 9. Ket luan

Huong lam tot nhat luc nay la khong day Vercel len lam muc tieu chinh qua som. Nen lam local AI that chac truoc:

1. Label dung.
2. Model tot nhat duoc luu dung.
3. Backend local predict on dinh.
4. Frontend dung Python API muot.

Khi cac phan nay da on, viec chuan bi Vercel chi con la buoc convert model sang TF.js va test browser inference.
