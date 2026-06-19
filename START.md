# 蹇€熷惎鍔ㄦ寚鍗?

## 绗竴娆′娇鐢?

### 姝ラ 1锛氬垵濮嬪寲鐜

**Windows锛堟帹鑽愶級锛?* 鍙屽嚮鏍圭洰褰曠殑 `setup.bat`锛岃嚜鍔ㄥ畬鎴愪互涓嬫墍鏈夋搷浣滐細
- 鍒涘缓 `.venv` 铏氭嫙鐜
- 瀹夎鍏ㄩ儴渚濊禆
- 浠?`.env.example` 鐢熸垚 `.env`
- 妫€鏌ョ煡璇嗗簱锛坉b_data\2d-v.db锛?

**Linux锛?* 鎵嬪姩鎵ц锛?
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

`.env.example` 宸插寘鍚彲鐢ㄧ殑 API Key锛屽鍒跺悗**鏃犻渶淇敼**鍗冲彲鍚姩銆?

濡傞渶鍒囨崲 API 閰嶇疆锛岀紪杈?`.env` 鍗冲彲銆?

---

### 姝ラ 2锛氬畨瑁?Poppler锛圵indows 蹇呴渶锛孡inux 璺宠繃锛?

1. 涓嬭浇锛歨ttps://github.com/oschwartz10612/poppler-windows/releases/
2. 瑙ｅ帇锛岃涓?`Library\bin` 鐨勫畬鏁磋矾寰?
3. 鍦?`.env` 鏈熬娣诲姞锛?
   ```
   POPPLER_PATH=D:\浣犵殑璺緞\poppler\Library\bin
   ```

Linux 涓€琛屾悶瀹氾細
```bash
sudo apt install poppler-utils
```

---

### 姝ラ 3锛氬畨瑁?FreeCAD 1.1锛堜笁瑙嗗浘鍔熻兘蹇呴渶锛?

- **Windows**锛氫粠 https://www.freecad.org 涓嬭浇瀹夎锛岀郴缁熻嚜鍔ㄦ壘鍒拌矾寰?
- **Linux**锛?
  ```bash
  sudo add-apt-repository ppa:freecad-maintainers/freecad-stable
  sudo apt update && sudo apt install freecad xvfb
  ```

---

## 鏃ュ父鍚姩

### Windows

```bat
updated_front\start_flask_demo.bat
```

鑴氭湰鑷姩绛夊緟鏈嶅姟灏辩华鍚庢墦寮€娴忚鍣紝鏃犻渶鎵嬪姩璁块棶鍦板潃銆?

> 鎵嬪姩鍚姩锛歚.venv\Scripts\python -m backend.run`锛岀劧鍚庤闂?**http://localhost:5190/dev/demo-industrial-console**

### Linux 鏈嶅姟鍣?

```bash
source .venv/bin/activate
xvfb-run -a python -m backend.run
```

> `xvfb-run` 涓?FreeCAD 鎻愪緵铏氭嫙鏄剧ず锛屾棤姝ゅ懡浠ゆ埅鍥惧姛鑳戒細澶辫触銆?

---

## 鍩烘湰鎿嶄綔

### 涓婁紶 PRT 鏂囦欢鐢熸垚宸ヨ壓

1. 鎵撳紑 http://localhost:5190/dev/demo-industrial-console
2. 鐐瑰嚮宸︿晶銆?*涓婁紶 PRT**銆嶏紝閫夋嫨 `.prt` 鎴?`.prt.N` 鏂囦欢
3. 鍙充晶杩涘害鏉′緷娆℃樉绀猴細
   - OnShape 杞崲锛堢害 30鈥?0 绉掞級
   - FreeCAD 涓夎鍥炬埅鍥撅紙绾?20鈥?0 绉掞級
   - 鍑犱綍 + VLM 鐗瑰緛鎻愬彇锛堢害 10鈥?0 绉掞級
4. 寮瑰嚭銆?*鐗瑰緛瀹￠槄**銆嶇晫闈紝鍙紪杈戞彁鍙栫殑鐗瑰緛鏂囨湰
5. 鐐瑰嚮銆?*纭骞剁敓鎴?*銆?
6. 绛夊緟宸ヨ壓鐢熸垚锛堢害 20鈥?0 绉掞級
7. 鍦ㄣ€屽伐鑹鸿绋嬨€嶆爣绛鹃〉鏌ョ湅缁撴灉锛岀偣鍑汇€?*瀵煎嚭 Excel**銆嶄笅杞?

### 涓婁紶 PDF 鏂囦欢

娴佺▼涓?PRT 鐩稿悓锛岃烦杩?OnShape 鍜?FreeCAD 姝ラ锛岀洿鎺ヨ繘琛岃瑙夊垎鏋愩€?

### 鎵归噺瀵煎叆鐭ヨ瘑搴擄紙ZIP锛?

1. 鍑嗗 ZIP锛氭瘡涓浂浠堕渶鍖呭惈 `.prt`/`.prt.N` + 瀵瑰簲鐨?`.xlsx` 宸ヨ壓
2. 宸︿晶闈㈡澘鍒囨崲鍒般€?*鐭ヨ瘑搴撳鍏?*銆嶆爣绛?
3. 涓婁紶 ZIP锛岄€夋嫨鐩爣宸ヨ壓搴?
4. 绛夊緟澶勭悊瀹屾垚

### 鍒囨崲浜戞ā寮?/ 鏈湴妯″紡锛圵indows锛?

鎵嬪姩灏?`backend/config_cloud.json` 鎴?`backend/config_local.json` 澶嶅埗涓?`backend/config.json`锛?
- **config_cloud.json**锛氫娇鐢ㄤ簯绔?DeepSeek + 璞嗗寘锛堥渶鑱旂綉锛?
- **config_local.json**锛氫娇鐢ㄦ湰鍦?vLLM锛堥渶鍐呯綉鏈嶅姟鍣?192.168.2.24:8000锛?

---

## 鎺掓煡闂

| 鐜拌薄 | 鍘熷洜 | 瑙ｅ喅 |
|------|------|------|
| 椤甸潰鎵撲笉寮€ | 鏈嶅姟鏈惎鍔?| 纭 `python -m backend.run` 鍦ㄨ繍琛岋紝绔彛 5190 鏈鍗犵敤 |
| OnShape 杞崲瓒呮椂 | 缃戠粶鎴栧嚟璇侀棶棰?| 妫€鏌?`.env` 涓?`onshape_credentials/did/wid`锛岀‘璁よ兘璁块棶 cad.onshape.com |
| 涓夎鍥炬埅鍥惧け璐ワ紙Linux锛?| 鏃犺櫄鎷熸樉绀?| 鐢?`xvfb-run -a` 鍚姩 |
| PDF 鎶?Poppler 閿欒 | Poppler 鏈畨瑁呮垨璺緞閿?| Windows锛氶厤缃?`POPPLER_PATH`锛汱inux锛歚apt install poppler-utils` |
| VLM 鐗瑰緛鎻愬彇璺宠繃 | API 鏈厤缃?| 纭 `.env` 涓?`VISION_API_KEY/BASE/MODEL_ID` 鏈夊€?|
| RAG 妫€绱㈡棤缁撴灉 | 鏁版嵁搴撶己澶?| 纭 `db_data/2d-v.db` 瀛樺湪 |

