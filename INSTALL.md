# 杩佺Щ鍒版柊鏈哄櫒 - 瀹夎鎸囧崡

## 鍓嶇疆杞欢锛堟墜鍔ㄥ畨瑁咃級

| 杞欢 | 鐗堟湰瑕佹眰 | 涓嬭浇鍦板潃 |
|------|---------|---------|
| Python | 3.11.x | https://www.python.org/downloads/release/python-3119/ |
| FreeCAD | 1.1 | https://www.freecad.org/downloads.php |
| Git | 浠绘剰 | https://git-scm.com/downloads |

> Poppler锛圥DF杞浘鐗囷級鍙€夛紝浠呭湪澶勭悊 PDF 鏃堕渶瑕併€?

---

## 蹇€熷紑濮?

### 绗竴姝ワ細鑾峰彇浠ｇ爜

```bat
git clone <浠撳簱鍦板潃>
cd 2D-v
```

鎴栬€呯洿鎺ュ鍒舵暣涓」鐩枃浠跺す锛堥渶鍖呭惈 `db_data\` 鐩綍锛夈€?

### 绗簩姝ワ細涓€閿垵濮嬪寲鐜

鍙屽嚮鎴栧湪 cmd 涓繍琛岋細

```bat
setup.bat
```

鑴氭湰浼氳嚜鍔ㄥ畬鎴愶細
- 鍒涘缓 Python 铏氭嫙鐜 `.venv`
- 瀹夎鎵€鏈変緷璧栵紙`backend\requirements.txt`锛?
- 浠?`.env.example` 鐢熸垚 `.env`
- 妫€鏌ョ煡璇嗗簱锛坉b_data\2d-v.db锛?

### 绗笁姝ワ細鍚姩绯荤粺

```bat
updated_front\start_flask_demo.bat
```

娴忚鍣ㄤ細鑷姩鎵撳紑 `http://127.0.0.1:5190`銆?

---

## FreeCAD 璺緞涓嶅湪榛樿浣嶇疆

濡傛灉 FreeCAD 瀹夎鍦ㄩ潪榛樿璺緞锛岀紪杈?`.env` 鍔犲叆锛?

```
FREECAD_BIN=D:\浣犵殑璺緞\FreeCAD 1.1\bin
FREECAD_LIB=D:\浣犵殑璺緞\FreeCAD 1.1\lib
```

---

## 杩佺Щ娉ㄦ剰浜嬮」

| 鏂囦欢/鐩綍 | 鏄惁鍦?git 涓?| 璇存槑 |
|-----------|--------------|------|
| `db_data\2d-v.db` | 鏄紝`git clone` 鑷姩鑾峰彇 | 鑻ュ師鏈哄櫒鏈夋湭鎻愪氦鐨勬柊鏁版嵁锛岄渶鎵嬪姩 `git push` 鍚庡啀 `clone` |
| `.env` | **鍚?* | `setup.bat` 浼氳嚜鍔ㄤ粠 `.env.example` 鐢熸垚 |

---

## 甯歌闂

**Q: `setup.bat` 鎶?Python鏈壘鍒?**  
A: 瀹夎 Python 3.11 鏃跺嬀閫?**"Add Python to PATH"**锛岀劧鍚庨噸鏂版墦寮€ cmd銆?

**Q: 鍚姩鍚庝笂浼?PRT 鏂囦欢鎶ラ敊**  
A: 妫€鏌?FreeCAD 璺緞鏄惁姝ｇ‘锛屾煡鐪?`backend.log` 鑾峰彇璇︾粏閿欒銆?

**Q: 鐭ヨ瘑搴撴绱㈣繑鍥炵┖**  
A: 纭 `db_data\2d-v.db` 瀛樺湪锛坄git clone` 鑷姩鑾峰彇锛涜嫢鍘熸満鍣ㄦ湁鏂版暟鎹渶鍏?`git push`锛夈€?

