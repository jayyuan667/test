# 浜岀淮宸ヨ壓绯荤粺 鈥?鍓嶇鎺у埗鍙?
> 鍩轰簬 2D 宸ヨ壓鍥剧焊鐨?AI 鐗瑰緛鎻愬彇銆佸伐鑹鸿绋嬭嚜鍔ㄧ敓鎴愩€佺煡璇嗗簱绠＄悊涓€浣撳寲 Web 鍓嶇銆?
## 鐩綍

- [椤圭洰姒傝](#椤圭洰姒傝)
- [鎶€鏈爤](#鎶€鏈爤)
- [椤圭洰缁撴瀯](#椤圭洰缁撴瀯)
- [椤甸潰鏋舵瀯涓庢ā鍧楄鏄嶿(#椤甸潰鏋舵瀯涓庢ā鍧楄鏄?
- [鏍稿績鍓嶇瀹炵幇閫昏緫](#鏍稿績鍓嶇瀹炵幇閫昏緫)
- [鍚庣 API 鑱斿姩璇﹁В](#鍚庣-api-鑱斿姩璇﹁В)
- [鏁版嵁娴佸叏閾捐矾](#鏁版嵁娴佸叏閾捐矾)
- [鍚姩鏂瑰紡](#鍚姩鏂瑰紡)

---

## 椤圭洰姒傝

鏈」鐩槸涓€涓?*宸ヤ笟宸ヨ壓瑙勭▼鑷姩鐢熸垚绯荤粺**鐨勫墠绔帶鍒跺彴銆傜敤鎴蜂笂浼?2D 宸ヨ壓鍥剧焊锛圥DF/PNG/JPG锛夋垨 PRT 涓夌淮妯″瀷锛岀郴缁熼€氳繃 AI锛圴LM 瑙嗚璇█妯″瀷 + RAG 妫€绱㈠寮虹敓鎴愶級鑷姩鎻愬彇闆朵欢鐗瑰緛骞剁敓鎴愬姞宸ュ伐鑹鸿绋嬨€傚墠绔彁渚涘畬鏁寸殑宸ヨ壓鍏ュ簱銆佺壒寰佸闃呫€佸伐鑹虹敓鎴愩€佸巻鍙茶褰曞洖鐪嬪拰鏁版嵁搴撴祻瑙堝姛鑳姐€?
**鏍稿績涓氬姟娴佺▼锛?*

```
涓婁紶鍥剧焊/妯″瀷 鈫?AI 鐗瑰緛鎻愬彇 鈫?浜哄伐瀹￠槄纭 鈫?宸ヨ壓瑙勭▼鐢熸垚 鈫?瀵煎嚭/鍏ュ簱
```

---

## 鎶€鏈爤

| 灞傛 | 鎶€鏈?|
|------|------|
| 椤甸潰缁撴瀯 | 鍘熺敓 HTML5锛屽崟鏂囦欢 `demo-industrial-console.html` |
| 鏍峰紡 | 鍘熺敓 CSS锛坄industrial-console.css`锛岀害 5000 琛屽伐涓氶璁捐绯荤粺锛?|
| 浜や簰閫昏緫 | 鍘熺敓 JavaScript锛坄demo-industrial-console.js`锛岀害 5000+ 琛岋級 |
| 3D 棰勮 | Three.js + GLTFLoader锛堟ā鍧楀寲寮曞叆锛?|
| 鏍囨敞宸ュ叿 | 鑷爺 SVG BoundingBox 鏍囨敞妯″潡锛坄annotation-tool.js`锛?|
| PDF 瀵煎嚭 | Vue 3 缁勪欢 `export-file-modal.vue`锛屼娇鐢?jsPDF + OPPOSans 瀛椾綋 |
| 鍚庣閫氫俊 | Fetch API + SSE锛圫erver-Sent Events锛夐暱杩炴帴 |
| 鍚庣 | Python Flask锛岀鍙?5190锛孲QLite 鏁版嵁搴?|

---

## 椤圭洰缁撴瀯

```
updated_front/
鈹溾攢鈹€ demo-industrial-console.html    # 涓?HTML锛堟墍鏈夐〉闈㈢粨鏋勪笌寮圭獥锛?鈹溾攢鈹€ css/
鈹?  鈹斺攢鈹€ industrial-console.css      # 鍏ㄩ噺鏍峰紡锛堝伐涓氶璁捐绯荤粺锛?鈹溾攢鈹€ js/
鈹?  鈹溾攢鈹€ demo-industrial-console.js  # 鏍稿績涓氬姟閫昏緫锛堢姸鎬佺鐞嗐€丄PI 璋冪敤銆丏OM 娓叉煋锛?鈹?  鈹溾攢鈹€ annotation-tool.js          # SVG 鏍囨敞宸ュ叿锛圔oundingBox 鏍囨敞绫伙級
鈹?  鈹溾攢鈹€ three-init.js               # Three.js 鍒濆鍖栦笌 GLTFLoader 鎸傝浇
鈹?  鈹溾攢鈹€ three.module.min.js         # Three.js 搴撴枃浠?鈹?  鈹溾攢鈹€ GLTFLoader.js               # Three.js GLTF 鍔犺浇鍣?鈹?  鈹斺攢鈹€ BufferGeometryUtils.js      # Three.js 鍑犱綍宸ュ叿
鈹溾攢鈹€ export-file-modal.vue           # Vue 3 PDF 瀵煎嚭缁勪欢锛堢嫭绔嬩簬涓诲簲鐢級
鈹溾攢鈹€ start_flask_demo.bat            # 涓€閿惎鍔ㄨ剼鏈紙鍚姩鍚庣 + 鎵撳紑娴忚鍣級
鈹溾攢鈹€ stop_flask_demo.bat             # 涓€閿仠姝㈣剼鏈?鈹溾攢鈹€ kb_import_selftest.zip          # 鐭ヨ瘑搴撳鍏ヨ嚜娴嬬敤绀轰緥 ZIP
鈹斺攢鈹€ system/                         # 绯荤粺璧勬簮鐩綍锛堝綋鍓嶄负绌猴級
```

---

## 椤甸潰鏋舵瀯涓庢ā鍧楄鏄?
绯荤粺閲囩敤**渚ф爮瀵艰埅 + 鍗曢〉鍒囨崲**鏋舵瀯锛屽叡 4 涓富椤甸潰锛?
### 1. 宸ヨ壓鍏ュ簱锛坄page-zip`锛?
**鍔熻兘锛?* 閫氳繃涓婁紶 ZIP 宸ヨ壓鍖呮壒閲忓鍏ュ伐鑹虹煡璇嗗埌鏁版嵁搴撱€?
- **鍏ュ簱鐩爣閫夋嫨锛?* 鏀寔閫夋嫨宸叉湁搴撴垨鏂板缓绉佹湁宸ヨ壓搴擄紝鍙€夊鍒跺叕鍏卞簱鍩虹嚎
- **鍐茬獊妯″紡锛?* 鏇挎崲鍏ュ簱 / 淇濈暀鏃х増
- **鐘舵€佸尯锛?* 绌洪棽 鈫?涓婁紶涓?鈫?瑙ｆ瀽涓?鈫?鍏ュ簱涓?鈫?瀹屾垚锛屽甫杩涘害鏉″拰瀹炴椂闃舵鎻愮ず
- **缁撴灉鍖猴細** 宸插尮閰嶈褰曞崱鐗囥€佹湭鍖归厤椤瑰垪琛ㄣ€佹壒娆℃棩蹇椾笁涓?Tab

### 2. 宸ヨ壓鐢熸垚锛坄page-generate`锛?
**鍔熻兘锛?* 涓婁紶鍗曚釜鍥剧焊/妯″瀷锛孉I 鑷姩鎻愬彇鐗瑰緛骞剁敓鎴愬伐鑹鸿绋嬨€?
- **宸︿晶涓婁紶闈㈡澘锛?* 鎷栨嫿涓婁紶鍖哄煙锛屼笂浼犲悗鍒囨崲涓哄浘绾搁瑙堬紙鏀寔澶氶〉缈婚〉銆佺缉鏀俱€佸叏灞忥級
- **鍙充晶缁撴灉闈㈡澘锛?*
  - **鐗瑰緛瀹￠槄 Tab锛?* 琛ㄦ牸鍖栧睍绀?AI 鎻愬彇鐨勫伐鑹虹壒寰侊紙灏哄鍏樊銆佺矖绯欏害銆佸舰浣嶅叕宸瓑锛夛紝鏀寔 `contenteditable` 鍘熶綅缂栬緫
  - **宸ヨ壓瑙勭▼ Tab锛?* 鎵撳瓧鏈哄姩鐢婚€愯杈撳嚭宸ュ簭琛紙宸ュ簭鍙枫€佸伐绉嶃€佸伐搴忓唴瀹癸級锛屾敮鎸佺紪杈?- **椤堕儴 HUD锛?* 缁熶竴杩涘害鏉?+ 闃舵鎻愮ず锛堝甫鍛煎惛鐏姩鐢伙級锛屽彲鎶樺彔
- **宸ュ叿鏍忥細** 涓婁紶鏂囦欢銆侀€夋嫨妫€绱㈢煡璇嗗簱銆佺壒寰佺紦瀛樺紑鍏炽€侀噸缃伐浣滃尯

### 3. 鍘嗗彶璁板綍锛坄page-list`锛?
**鍔熻兘锛?* 娴忚鎵€鏈夊巻鍙插伐鑹虹敓鎴愪换鍔°€?
- **缁熻鍗＄墖锛?* 鎬绘暟銆佸凡瀹屾垚銆佸緟瀹￠槄銆佹€诲伐搴忔暟
- **琛ㄦ牸锛?* 浠诲姟鍚?妯″瀷銆佺姸鎬併€佸畬鎴愭椂闂淬€佸伐搴忔暟銆佸揩鐓ф煡鐪嬨€佸垹闄?- **鍒嗛〉锛?* 鏀寔鎸夊畬鎴愭棩鏈熺瓫閫夛紝鎵归噺閫夋嫨鍒犻櫎
- **蹇収寮圭獥锛?* 鍒嗘爮棰勮锛堝乏鍥惧彸鏂囷級锛屾敮鎸佸浘鐗囩缉鏀?缈婚〉銆?D 妯″瀷棰勮锛圙LTF锛夈€佺壒寰佸闃呭拰宸ヨ壓瑙勭▼璇︽儏

### 4. 鏁版嵁搴撴祻瑙堬紙`page-db`锛?
**鍔熻兘锛?* 娴忚鍜岀紪杈戠煡璇嗗簱涓殑宸ヨ壓璁板綍銆?
- **璁块棶鎺у埗锛?* 榛樿閿佸畾锛岄渶鍏堝畬鎴愪竴娆?ZIP 鍏ュ簱鎵嶈В閿佺紪杈戝姛鑳斤紱鏀寔鍙娴忚鍏叡搴?涓汉搴?- **涓夋爮甯冨眬锛?* 宸︿晶绛涢€夐潰鏉匡紙鍏抽敭璇嶃€佷骇鍝佺被鍨嬨€佹潵婧愩€佺姸鎬侊級銆佷腑闂磋褰曞垪琛ㄣ€佸彸渚ц鎯呴潰鏉?- **璇︽儏闈㈡澘锛?* 璁板綍鍏冩暟鎹€佹ā鍨嬪揩鐓ф煡鐪嬨€佸伐鑹哄唴瀹圭紪杈戙€佺壒寰佹姤鍛婃寜椤电紪杈?- **鎿嶄綔锛?* 缂栬緫璁板綍銆佸垹闄ゅ簾琛ㄣ€佸垹闄ゆ暣涓敤鎴峰簱锛堝叕鍏卞簱鍙淇濇姢锛?
---

## 鏍稿績鍓嶇瀹炵幇閫昏緫

### 鐘舵€佺鐞嗭紙`backendState` 瀵硅薄锛?
鏁翠釜搴旂敤浣跨敤涓€涓叏灞€ `backendState` 瀵硅薄绠＄悊鎵€鏈夌姸鎬侊紝鍖呮嫭锛?
```javascript
backendState = {
  history: [],                    // 鍘嗗彶浠诲姟鍒楄〃
  records: [],                    // 鏁版嵁搴撹褰?  taskMap: {},                    // 浠诲姟妲戒綅 鈫?浠诲姟鍗＄墖鏁版嵁鏄犲皠
  latestTaskId: '',               // 鏈€鏂颁换鍔?ID
  latestResult: null,             // 鏈€鏂颁换鍔＄粨鏋?  latestZipReport: null,          // 鏈€鏂?ZIP 鍏ュ簱鎶ュ憡
  activeLibraryKey: 'public',     // 褰撳墠娲昏穬鐭ヨ瘑搴?key
  retrievalLibraryKey: 'public',  // 褰撳墠妫€绱㈠簱 key
  canBrowseDb: false,             // 鏁版嵁搴撴槸鍚﹀彲娴忚
  dbBrowseOnly: false,            // 鏄惁鍙妯″紡
  taskBusy: false,                // 浠诲姟鏄惁杩涜涓?  taskProgress: 0,                // 浠诲姟杩涘害鐧惧垎姣?  previewImages: [],              // 棰勮鍥剧墖 URL 鍒楄〃
  previewIndex: 0,                // 褰撳墠棰勮鍥剧墖绱㈠紩
  previewZoom: 1,                 // 棰勮缂╂斁姣?  processStreamText: '',          // SSE 娴佸紡宸ヨ壓鏂囨湰绱Н
  processStreamRows: [],          // 瑙ｆ瀽鍚庣殑宸ヨ壓琛?  twRowQueue: [],                 // 鎵撳瓧鏈哄姩鐢婚槦鍒?  twIsTyping: false,              // 鎵撳瓧鏈烘槸鍚︽鍦ㄨ緭鍑?  featureCacheEnabled: false,     // 鐗瑰緛缂撳瓨寮€鍏?  // ...
}
```

### DOM 寮曠敤妯″紡

鎵€鏈?DOM 鍏冪礌鍦ㄨ剼鏈《閮ㄩ€氳繃 `document.getElementById` 鑾峰彇骞剁紦瀛樹负甯搁噺锛堢害 150+ 涓紩鐢級锛屽悗缁搷浣滅洿鎺ヤ娇鐢ㄨ繖浜涘紩鐢紝閬垮厤閲嶅鏌ヨ銆?
### 椤甸潰鍒囨崲

閫氳繃 `activatePage(pageId)` 鍑芥暟鎺у埗锛氶殣钘忔墍鏈?`.page`锛屾樉绀虹洰鏍囬〉闈紝鏇存柊渚ф爮 `.nav-item.active` 鐘舵€併€傚鑸椂浼氭鏌ユ槸鍚︽湁杩涜涓殑浠诲姟锛圸IP 瀵煎叆鎴栧伐鑹虹敓鎴愶級锛屾湁鍒欓攣瀹氬叾浠栭〉闈€?
### 鎵撳瓧鏈哄姩鐢诲紩鎿庯紙`tw*` 绯诲垪鍑芥暟锛?
宸ヨ壓瑙勭▼鐨勬祦寮忚緭鍑洪噰鐢ㄨ嚜鐮旀墦瀛楁満寮曟搸锛?
1. **`queueProcessStreamChunk(taskId, chunk)`** 鈥?鎺ユ敹 SSE 鎺ㄩ€佺殑鏂囨湰鍧楋紝閫愬瓧绗﹀杺鍏?`twFeedChar`
2. **`twFeedChar(ch)`** 鈥?閫愬瓧绗︾疮绉埌琛岀紦鍐插尯锛岄亣鍒?`\n` 鏃惰В鏋愪负宸ュ簭琛岋紙`0010@宸ョ@鍐呭` 鏍煎紡锛?3. **`twStartNextRow()`** 鈥?浠庨槦鍒楀彇鍑轰竴琛岋紝鍒涘缓 `<tr>` DOM锛岃皟鐢?`twTypeFieldSequence` 閫愬瓧娈垫墦瀛?4. **`twTypeField(el, text, speed, onDone)`** 鈥?閫愬瓧绗﹁緭鍑哄埌 DOM 鍏冪礌锛屼腑鏂?鏍囩偣/鏁板瓧浣跨敤涓嶅悓寤惰繜妯℃嫙鐪熶汉鎵撳瓧鑺傚
5. **`twFinishRow(tr, row)`** 鈥?琛屽畬鎴愬姩鐢伙紙`row-new` CSS 鍔ㄧ敾锛夛紝鏆傚仠 320-600ms 鍚庡紑濮嬩笅涓€琛?6. **`twOnAllRowsDone()`** 鈥?鍏ㄩ儴琛屽畬鎴愬悗瑙﹀彂鏈€缁堟覆鏌撱€佺姸鎬佸悓姝ュ拰鍘嗗彶璁板綍鏇存柊

### 鏍囨敞宸ュ叿锛坄annotation-tool.js`锛?
`AnnotationTool` 绫绘彁渚涘熀浜?SVG 鐨勭煝閲忕煩褰㈡爣娉ㄥ姛鑳斤紝鐢ㄤ簬鍦?2D 鍥剧焊涓婁汉宸ユ爣璁板伐鑹虹壒寰佸尯鍩燂紙鍊掕銆佽灪绾瑰瓟銆佸渾瀛旂瓑锛夛紝涓哄悗缁?AI 鐗瑰緛鎻愬彇鎻愪緵璁粌鏁版嵁銆?
#### 鏍囩绯荤粺

鍐呭缓涓夌被鏍囩锛屽悇鏈夌嫭绔嬬殑 `id`銆侀鑹层€佽櫄绾挎牱寮忥細

| 閿悕 | id | 棰滆壊 | 铏氱嚎 | 涓枃 |
|------|----|------|------|------|
| `chamfer` | 2 | `#f59e0b` | 鏃?| 鍊掕 |
| `threaded_hole` | 0 | `#6366f1` | `6,3` | 铻虹汗瀛?|
| `circle_hole` | 1 | `#10b981` | 鏃?| 鍦嗗瓟 |

- **鑷畾涔夋爣绛撅細** 鐢ㄦ埛鍙€氳繃 `prompt` 杈撳叆涓枃鍚嶇О鏂板鏍囩锛屼粠 5 鑹插惊鐜睜锛坄#ec4899`, `#14b8a6`, `#f97316`, `#8b5cf6`, `#06b6d4`锛夎嚜鍔ㄥ彇鑹?- **鎸佷箙鍖栵細** 鑷畾涔夋爣绛惧瓨鍌ㄥ湪 `localStorage` key `annotate.customLabels.v1`锛岄〉闈㈠埛鏂板悗淇濈暀
- **瀹夊叏鍒犻櫎锛?* 鍒犻櫎鑷畾涔夋爣绛惧墠浼氭壂鎻忔墍鏈夐〉闈㈢殑鏍囨敞鏁版嵁锛岃嫢浠嶆湁寮曠敤鍒欐嫆缁濆垹闄ゅ苟鎻愮ず椤垫暟
- **鍏ㄥ眬鏆撮湶锛?* `getAnnotationLabelMeta()` 鎸傝浇鍒?`window`锛屼緵涓诲簲鐢紙`demo-industrial-console.js`锛夋覆鏌撴爣娉ㄦ眹鎬诲崱鐗囨椂鑾峰彇棰滆壊鍜屼腑鏂囧悕

#### 鍧愭爣绯荤粺

SVG 閫氳繃 `position: absolute; inset: 0` 瑕嗙洊鍦?`<img>` 涓婏紝涓よ€呭浜庡悓涓€涓?`inline-block` 瀹瑰櫒鍐咃細

- **`_imgOffset()`锛?* 鐢?`getBoundingClientRect()` 鍒嗗埆鑾峰彇 `<img>` 鍜?`<svg>` 鐨勭煩褰紝璁＄畻鍋忕Щ閲?`(dx, dy)` 鍜岀缉鏀炬瘮 `(sx, sy)`銆備娇鐢?`getBoundingClientRect` 鑰岄潪 `clientWidth` 鏄负浜嗗吋瀹圭鍏堝厓绱犱笂鐨?CSS transform
- **`_toReal(svgX, svgY)`锛?* SVG 鍍忕礌鍧愭爣 鈫?鍥剧墖鑷劧鍧愭爣锛堝噺鍋忕Щ銆侀櫎缂╂斁姣旓級
- **`_toDisplay(realX, realY)`锛?* 鍥剧墖鑷劧鍧愭爣 鈫?SVG 鍍忕礌鍧愭爣锛堜箻缂╂斁姣斻€佸姞鍋忕Щ锛?- 鎵€鏈夋爣娉ㄧ殑 `points` 瀛楁瀛樺偍鐨勬槸**鍥剧墖鑷劧鍧愭爣** `[[x1,y1], [x2,y2]]`锛屾覆鏌撴椂瀹炴椂鎹㈢畻涓烘樉绀哄潗鏍囷紝鍥犳缂╂斁涓嶅奖鍝嶆爣娉ㄧ簿搴?
#### 缁樺埗娴佺▼

1. `mousedown`锛堝乏閿級锛氳褰曡捣濮嬬偣锛屽垱寤?`<rect>` 鑽夌鐭╁舰锛堝崐閫忔槑濉厖 + 褰撳墠鏍囩棰滆壊鎻忚竟锛宍pointer-events: none`锛?2. `mousemove`锛氬疄鏃舵洿鏂拌崏绋跨煩褰㈢殑 `x/y/width/height`锛堝彇 `Math.min` 澶勭悊鍙嶅悜鎷栨嫿锛?3. `mouseup`锛氱Щ闄よ崏绋跨煩褰紝鑻ユ嫋鎷借窛绂?鈮?6px 鍒欏皢璧锋鐐归€氳繃 `_toReal` 杞负鑷劧鍧愭爣锛宲ush 鍒?`_annotations` 鏁扮粍锛岃Е鍙?`renderAll()` + `_renderList()` + `_scheduleSave()`
4. 鍙抽敭鐐瑰嚮宸叉湁鏍囨敞妗?鈫?鍒犻櫎璇ユ爣娉?
#### 澶氶〉鏀寔

- `_allPages` 瀵硅薄浠ラ〉鐮佸瓧绗︿覆锛坄"1"`, `"2"`, ...锛変负閿紝瀛樺偍姣忛〉鐨勬爣娉ㄦ暟缁?- 鍒囨崲椤甸潰鏃讹紙`_goPage`锛夎嚜鍔ㄤ繚瀛樺綋鍓嶉〉鍒?`_allPages`锛屽啀鍔犺浇鐩爣椤电殑鏍囨敞
- `_loadPage(idx)` 璁剧疆 `<img>` 鐨?`src`锛屽浘鐗囧姞杞藉畬鎴愬悗鑷姩璋冪敤 `fitToViewport()` 閫傞厤瑙嗗彛

#### 閫変腑鎬佹覆鏌?
`renderAll()` 鎸夐€変腑鐘舵€佹帓搴忥紝閫変腑妗嗘渶鍚庣粯鍒讹紙淇濊瘉鍦ㄦ渶涓婂眰锛夛細

- **鍏夋檿鏁堟灉锛?* 閫変腑鏍囨敞澶栧眰娓叉煋鐧借壊鎻忚竟锛坄stroke: #ffffff, width: 6`锛? 榛戣壊铏氱嚎鐜紙`stroke: #111827, dash: 6 4`锛夛紝鍦嗚 `rx=4`
- **娴姩鏍囩锛?* 浠呴€変腑鏃跺湪妗嗕笂鏂规樉绀鸿嵂涓稿舰鏍囩锛堝"铻虹汗瀛?3"锛夛紝鑳屾櫙鑹插彇鏍囩鑹诧紝鐧借壊鏂囧瓧锛岄伩鍏嶆湭閫変腑妗嗙殑鏍囩閬尅
- **鐙珛缂栧彿锛?* 鎸夋爣绛剧被鍨嬬嫭绔嬮€掑搴忓彿锛堝€掕 1銆佸€掕 2銆佽灪绾瑰瓟 1鈥︼級锛孲VG 鏍囩鏂囧瓧涓庡彸渚у垪琛ㄥ簭鍙蜂弗鏍间竴鑷?
#### 鍙屽悜鑱斿姩閫変腑

`_selectAnnotation(id, opts)` 鏀寔涓変釜鏉ユ簮锛?
| 鏉ユ簮 | `opts` | 婊氬姩琛屼负 |
|------|--------|----------|
| 鐢诲竷鐐瑰嚮 | `{ fromCanvas: true }` | 鍒楄〃婊氬姩鍒板搴旈」 |
| 鍒楄〃鐐瑰嚮 | `{ fromList: true }` | 鐢诲竷婊氬姩鍒板搴旂煩褰腑蹇?|
| 绋嬪簭璋冪敤 | `{}` | 涓や晶閮芥粴鍔?|

- 鐢诲竷婊氬姩閫氳繃 `_scrollCanvasToAnnotation()` 璁＄畻鏍囨敞涓績鐨勬樉绀哄潗鏍?鈫?杞负 scroll 瀹瑰櫒鍧愭爣 鈫?`scrollTo({ behavior: 'smooth' })`
- 鍒楄〃婊氬姩閫氳繃 `_scrollListToAnnotation()` 鐢?`querySelector` 鎸?`data-ann-id` 鎵惧埌 DOM 鍏冪礌 鈫?`scrollIntoView({ block: 'nearest' })`

#### 缂╂斁

- **鐘舵€侊細** `_zoom`锛堝綋鍓嶇缉鏀炬瘮锛夈€乣_fitZoom`锛堟渶杩戜竴娆?fit-to-viewport 璁＄畻鐨勭缉鏀炬瘮锛?- **鑼冨洿锛?* 0.05x ~ 8.0x
- **`_applyZoom()`锛?* 鐩存帴璁剧疆 `<img>` 鐨?`style.width/height` 涓?`naturalWidth * _zoom`锛屽悓鏃惰鐩?`max-width: none; max-height: none` 鍙栨秷 CSS 闄愬埗
- **Ctrl+婊氳疆缂╂斁锛?* 浠ュ厜鏍囦负涓績 鈥?缂╂斁鍓嶈褰曞厜鏍囦笅鐨勫浘鐗囪嚜鐒跺潗鏍?`(pxNat, pyNat)`锛岀缉鏀惧悗鍙嶇畻 scroll 鍋忕Щ浣胯鐐逛繚鎸佸湪鍏夋爣灞忓箷浣嶇疆
- **宸ュ叿鏍忔寜閽細** 鏀惧ぇ锛埫?.25锛夈€佺缉灏忥紙梅1.25锛夈€侀€傚簲瑙嗗彛锛坄fitToViewport`锛夈€?00%锛坄setZoom(1.0)`锛?- **`fitToViewport()`锛?* 鏍规嵁 scroll 瀹瑰櫒鍙敤瀹介珮锛堝噺鍘?28px padding锛夊拰鍥剧墖鑷劧灏哄璁＄畻 `Math.min(sx, sy)` 浣滀负 fit 缂╂斁姣?
#### 鎸佷箙鍖栨満鍒?
- **鑷姩淇濆瓨锛?* 鏍囨敞鍙樻洿鍚?`_scheduleSave()` 鍚姩 1s 闃叉姈瀹氭椂鍣紝瑙﹀彂 `_autoSaveNow()` POST 鍒?`/api/annotations/{taskId}/save`
- **淇濆瓨 payload锛?* `{ page, shapes: [{label, points}], imageWidth, imageHeight, imagePath }`
- **椤甸潰鍏抽棴鍏滃簳锛?* `sendBeaconSave()` 浣跨敤 `navigator.sendBeacon()` 鍙戦€?Blob JSON锛屾祻瑙堝櫒淇濊瘉鍦ㄩ〉闈㈠嵏杞藉悗浠嶈兘鍙戦€?- **鏈嶅姟绔姞杞斤細** `_loadFromServer()` GET `/api/annotations/{taskId}`锛岃繑鍥?`{ pages: { "1": { shapes: [...] }, ... } }`锛屽悎骞跺埌 `_allPages`
- **鐢熷懡鍛ㄦ湡锛?* `activate()` 娉ㄥ唽鎵€鏈変簨浠?鈫?`deactivate()` 杩斿洖 Promise锛堝彲 await 鏈€缁堜繚瀛樺畬鎴愶級鈫?娓呯悊 SVG 鍜屼簨浠剁洃鍚?- **`flushSave()`锛?* 鍏紑鏂规硶锛屼緵澶栭儴璋冪敤鏂圭瓑寰呬繚瀛樼粨鏉熷悗鍐嶆墽琛屽悗缁搷浣滐紙濡傚叧闂爣娉ㄩ潰鏉匡級
- **`getSummary()`锛?* 杩斿洖璺ㄦ墍鏈夐〉闈㈢殑鏍囨敞姹囨€?`{ chamfer: N, threaded_hole: N, circle_hole: N, pages: N }`锛屼富搴旂敤鐢ㄤ簬鍒锋柊寰呮爣娉ㄧ姸鎬佸崱鐗?
#### 瀵煎嚭

`_exportZip()` 鍏堣Е鍙?`_autoSaveNow()` 纭繚鏈嶅姟绔湁鏈€鏂版暟鎹紝600ms 鍚庡垱寤轰复鏃?`<a>` 鏍囩瑙﹀彂 `/api/annotations/{taskId}/export` 涓嬭浇锛屾枃浠跺悕涓?`annotations_{taskId}.zip`

### 3D 棰勮锛坄three-init.js`锛?
閫氳繃 `importmap` 寮曞叆 Three.js 妯″潡锛宍GLTFLoader` 鎸傝浇鍒?`window.THREE`銆俙make3DViewer()` 宸ュ巶鍑芥暟鍒涘缓 3D 鏌ョ湅鍣ㄥ疄渚嬶紝鏀寔 GLTF 妯″瀷鍔犺浇銆丱rbitControls 浜や簰锛堟嫋鎷芥棆杞?缂╂斁锛夈€傚湪鍘嗗彶蹇収鍜屾暟鎹簱棰勮涓敤浜庡睍绀?PRT 妯″瀷鐨勪笁缁磋鍥俱€?
### 瀵煎嚭鍔熻兘锛坄export-file-modal.vue`锛?
鐙珛鐨?Vue 3 缁勪欢锛屼娇鐢?jsPDF 鐢熸垚 A4 宸ヨ壓瑙勭▼鍗＄墖 PDF锛?
- 宸︿晶宓屽叆鍥剧焊棰勮鍥撅紝鍙充晶灞曠ず妯″瀷淇℃伅灞炴€ц〃
- 涓嬫柟涓哄伐鑹鸿绋嬭〃鏍硷紙宸ュ簭鍙枫€佸伐绉嶃€佸伐搴忓悕绉板強鍐呭銆佽澶囧瀷鍙枫€佸伐鏃讹級
- 鏀寔澶氳鑷姩鎹㈣銆佽法椤电画琛ㄣ€佹枒椹潯绾?- 浣跨敤鑷爺 `OPPOSans-L` 涓枃瀛椾綋宓屽叆

---

## 鍚庣 API 鑱斿姩璇﹁В

### API 鍩虹

```javascript
const API_BASE = window.__API_BASE__ || 'http://localhost:5190/api';
```

鎵€鏈夎姹傞€氳繃缁熶竴鐨?`apiFetch(path, options)` 灏佽锛岃嚜鍔ㄥ鐞?JSON Content-Type 鍜岄敊璇搷搴斻€?
### 瀹屾暣 API 绔偣娓呭崟

#### 1. 浠诲姟鐢熷懡鍛ㄦ湡

| 绔偣 | 鏂规硶 | 鐢ㄩ€?| 瑙﹀彂鏃舵満 |
|------|------|------|----------|
| `/api/upload` | POST | 涓婁紶鍗曚釜 PRT 妯″瀷 | 鐢ㄦ埛鍦ㄥ伐鑹虹敓鎴愰〉涓婁紶 PRT 鏂囦欢 |
| `/api/upload_drawing` | POST | 涓婁紶 2D 鍥剧焊锛圥DF/PNG/JPG锛?| 鐢ㄦ埛涓婁紶 2D 鍥剧焊锛岄檮甯?`library_key` 鍜?`use_cache` |
| `/api/batch_upload` | POST | 鎵归噺涓婁紶 PRT 妯″瀷 | 鐢ㄦ埛閫夋嫨澶氫釜 PRT 鏂囦欢 |
| `/api/result/{taskId}` | GET | 鑾峰彇浠诲姟缁撴灉锛堝惈宸ヨ壓瑙勭▼銆佺壒寰佹姤鍛娿€侀瑙堝浘锛?| 杞浠诲姟杩涘害 + 鑾峰彇鏈€缁堢粨鏋?|
| `/api/review/{taskId}` | POST | 鎻愪氦鐗瑰緛瀹￠槄纭/淇敼鍚庨噸鏂扮敓鎴?| 鐢ㄦ埛鍦ㄧ壒寰佸闃呴潰鏉跨‘璁ゆ垨淇敼鍚庨噸鏂扮敓鎴?|
| `/api/events/{taskId}` | SSE | 瀹炴椂浜嬩欢娴侊紙杩涘害鏇存柊銆佹祦寮忓伐鑹鸿緭鍑猴級 | 浠诲姟寮€濮嬪悗寤虹珛 EventSource 杩炴帴 |
| `/api/export/{taskId}` | POST | 瀵煎嚭宸ヨ壓鏂囦欢锛圥DF/Excel锛?| 鐢ㄦ埛鐐瑰嚮瀵煎嚭鎸夐挳锛岄檮甯﹀綋鍓嶇紪杈戝悗鐨?`rows` |

#### 2. 鐭ヨ瘑搴撶鐞?
| 绔偣 | 鏂规硶 | 鐢ㄩ€?|
|------|------|------|
| `/api/kb/import_zip` | POST | 涓婁紶 ZIP 宸ヨ壓鍖呮壒閲忓叆搴?|
| `/api/kb/sample_zip` | GET | 涓嬭浇绀轰緥 ZIP 宸ヨ壓鍖?|
| `/api/library/status` | GET | 鑾峰彇鐭ヨ瘑搴撶姸鎬侊紙鏄惁灏辩华銆佸彲娴忚銆佸簱鍒楄〃锛?|
| `/api/library/scopes` | GET | 鑾峰彇鎵€鏈夌煡璇嗗簱浣滅敤鍩燂紙鍏叡/绉佹湁搴撳垪琛級 |
| `/api/library/scopes/{key}` | DELETE | 鍒犻櫎鏁翠釜鐢ㄦ埛搴?|
| `/api/library/records` | GET | 鍒嗛〉鑾峰彇鐭ヨ瘑搴撹褰曪紙鏀寔绛涢€夛級 |
| `/api/library/records/{id}` | PUT | 鏇存柊鐭ヨ瘑搴撹褰曪紙浜у搧绫诲瀷銆佸伐鑹哄唴瀹广€佺壒寰佹姤鍛婏級 |
| `/api/library/records/{id}` | DELETE | 鍒犻櫎鍗曟潯鐭ヨ瘑搴撹褰?|

#### 3. 鍘嗗彶涓庢爣娉?
| 绔偣 | 鏂规硶 | 鐢ㄩ€?|
|------|------|------|
| `/api/history` | GET | 鑾峰彇鍘嗗彶浠诲姟鍒楄〃 |
| `/api/history/{taskId}` | DELETE | 鍒犻櫎鍘嗗彶浠诲姟 |
| `/api/annotations/{taskId}` | GET | 鑾峰彇鏍囨敞鏁版嵁 |
| `/api/annotations/{taskId}/save` | POST | 淇濆瓨鏍囨敞鏁版嵁锛圝SON body锛?|
| `/api/annotations/{taskId}/finalize` | POST | 鏍囨敞瀹屾垚锛岃Е鍙戝悗缁伐鑹虹敓鎴?|
| `/api/annotations/{taskId}/export` | GET | 瀵煎嚭鏍囨敞鏁版嵁涓?ZIP |

#### 4. 绯荤粺

| 绔偣 | 鏂规硶 | 鐢ㄩ€?|
|------|------|------|
| `/api/health` | GET | 鍚庣鍋ュ悍妫€鏌ワ紙鍚姩鑴氭湰鐢級 |
| `/api/startup_token` | GET | 鑾峰彇鍚姩浠ょ墝锛堟娴嬪悗绔噸鍚級 |

### 鍓嶅悗绔氦浜掓椂搴忓浘

#### 2D 鍥剧焊宸ヨ壓鐢熸垚瀹屾暣娴佺▼

```
鍓嶇                           鍚庣
 鈹?                             鈹? 鈹? POST /upload_drawing        鈹? 鈹? (file + library_key)        鈹? 鈹傗攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈫掆攤
 鈹? 鈫?{ task_id }               鈹? 鈹?                             鈹? 鈹? GET /events/{taskId}  (SSE) 鈹? 鈹傗攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈫掆攤
 鈹? 鈫?event: progress {10%}     鈹? 鈹? 鈫?event: log "鍥剧焊鍒嗘瀽涓?    鈹? 鈹? 鈫?event: progress {30%}     鈹? 鈹? 鈫?event: feature_report     鈹? 鈹?    { review_text, ... }     鈹? 鈹? 鈫?event: status "awaiting_review"
 鈹?                             鈹? 鈹? [鐢ㄦ埛瀹￠槄鐗瑰緛锛岀偣鍑荤‘璁       鈹? 鈹? POST /review/{taskId}       鈹? 鈹? { confirmed: true, ... }    鈹? 鈹傗攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈫掆攤
 鈹? 鈫?event: progress {50%}     鈹? 鈹? 鈫?event: process_chunk      鈹? 鈹?    "0010@鏂橜澶囨枡锛?.."       鈹? 鈹? 鈫?event: process_chunk      鈹? 鈹?    "0020@閾閾ｆ柟鍏潰..."     鈹? 鈹? 鈫?... (娴佸紡杈撳嚭)             鈹? 鈹? 鈫?event: progress {100%}    鈹? 鈹? 鈫?event: status "completed" 鈹? 鈹?                             鈹? 鈹? GET /result/{taskId}        鈹? 鈹? (鏈€缁堝畬鏁寸粨鏋?               鈹? 鈹傗攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈫掆攤
 鈹? 鈫?{ process_flow,           鈹? 鈹?    feature_report_text,     鈹? 鈹?    preview_image_urls, ... }鈹?```

#### ZIP 鐭ヨ瘑搴撳叆搴撴祦绋?
```
鍓嶇                           鍚庣
 鈹?                             鈹? 鈹? POST /kb/import_zip         鈹? 鈹? (zip_file + conflict_mode   鈹? 鈹?  + library_mode)            鈹? 鈹傗攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈫掆攤
 鈹? 鈫?{ batch_id, summary,      鈹? 鈹?    matched_pairs,           鈹? 鈹?    target_library }         鈹? 鈹?                             鈹? 鈹? GET /library/status         鈹? 鈹? (鍒锋柊搴撶姸鎬?                 鈹? 鈹傗攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈫掆攤
 鈹?                             鈹? 鈹? GET /library/records        鈹? 鈹? (鍒锋柊璁板綍鍒楄〃)               鈹? 鈹傗攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈫掆攤
```

### SSE 浜嬩欢绫诲瀷

閫氳繃 `EventSource` 杩炴帴 `/api/events/{taskId}`锛屽悗绔帹閫佷互涓嬩簨浠讹細

| 浜嬩欢鍚?| 鏁版嵁缁撴瀯 | 璇存槑 |
|--------|----------|------|
| `progress` | `{ progress: number }` | 浠诲姟杩涘害鏇存柊锛?-100锛?|
| `log` | `{ tag: string, text: string }` | 瀹炴椂鏃ュ織锛堟樉绀哄湪 HUD 闃舵鎻愮ず锛?|
| `feature_report` | `{ review_text, ... }` | 鐗瑰緛鎻愬彇鎶ュ憡锛堣Е鍙戝闃呴潰鏉挎覆鏌擄級 |
| `status` | `{ status: string }` | 鐘舵€佸彉鏇达紙`awaiting_review` / `completed` / `error`锛?|
| `process_chunk` | `{ text: string }` | 宸ヨ壓瑙勭▼娴佸紡鏂囨湰鍧楋紙鍠傚叆鎵撳瓧鏈哄紩鎿庯級 |
| `gltf_url` | `{ url: string }` | PRT 妯″瀷 3D 棰勮 URL |
| `preview_image` | `{ url: string }` | 棰勮鍥剧墖 URL |

### 鐗瑰緛缂撳瓨鏈哄埗

鍓嶇鎻愪緵 `鈿?鐗瑰緛缂撳瓨` 寮€鍏筹紙`backendState.featureCacheEnabled`锛夈€傚紑鍚悗锛屼笂浼犲浘绾告椂鍦?FormData 涓檮鍔?`use_cache=1`銆傚悗绔鍚屼竴浠藉浘绾革紙鎸夋枃浠?hash 鍒ゆ柇锛夎烦杩?VLM 鐗瑰緛鎻愬彇锛岀洿鎺ヨ繑鍥炰笂娆＄殑鍒嗘瀽缁撴灉锛屽姞蹇噸澶嶄笂浼犲満鏅殑鍝嶅簲閫熷害銆?
### 鐭ヨ瘑搴撳搴撴灦鏋?
绯荤粺鏀寔**澶氱煡璇嗗簱闅旂**锛?
- **鍏叡宸ヨ壓搴擄紙public锛夛細** 鍏ㄥ眬鍏变韩锛屽彧璇?- **鐢ㄦ埛绉佹湁搴擄細** 閫氳繃 ZIP 鍏ュ簱鍒涘缓锛屽彲缂栬緫/鍒犻櫎
- **妫€绱㈠簱閫夋嫨锛?* 宸ヨ壓鐢熸垚鏃跺彲閫夋嫨鐢ㄥ摢涓簱鍋?RAG 妫€绱紙`retrievalLibraryKey`锛夛紝榛樿鍏叡搴?- **鍏ュ簱鐩爣閫夋嫨锛?* ZIP 鍏ュ簱鏃跺彲閫夋嫨鐩爣搴擄紝鏀寔鏂板缓锛堝彲閫夊鍒跺叕鍏卞熀绾匡級

搴撶姸鎬侀€氳繃 `sessionStorage` 鎸佷箙鍖栵紙`ZIP_UNLOCK_SESSION_KEY` / `ZIP_SCOPE_SESSION_KEY` / `RETRIEVAL_SCOPE_SESSION_KEY`锛夛紝椤甸潰鍒锋柊鍚庢仮澶嶃€?
---

## 鏁版嵁娴佸叏閾捐矾

```
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?    鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?    鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?  鐢ㄦ埛涓婁紶    鈹傗攢鈹€鈹€鈹€鈫掆攤  Flask 鍚庣   鈹傗攢鈹€鈹€鈹€鈫掆攤  VLM 瑙嗚妯″瀷 鈹?鈹? PDF/PRT/ZIP 鈹?    鈹? /api/upload  鈹?    鈹? 鐗瑰緛鎻愬彇     鈹?鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?    鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹?    鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?                           鈹?                    SSE 鎺ㄩ€?鈹?杩涘害/鏃ュ織/鐗瑰緛
                           鈹?                    鈹屸攢鈹€鈹€鈹€鈹€鈹€鈻尖攢鈹€鈹€鈹€鈹€鈹€鈹€鈹?                    鈹? 鍓嶇 HUD     鈹?                    鈹? 瀹炴椂鏇存柊杩涘害  鈹?                    鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹?                           鈹?              鐗瑰緛鎶ュ憡鍒拌揪   鈹?                    鈹屸攢鈹€鈹€鈹€鈹€鈹€鈻尖攢鈹€鈹€鈹€鈹€鈹€鈹€鈹?                    鈹? 鐗瑰緛瀹￠槄闈㈡澘  鈹?鈫?鐢ㄦ埛缂栬緫/纭
                    鈹? 琛ㄦ牸鍖栧睍绀?   鈹?                    鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹?                           鈹?              POST /review  鈹?纭鐗瑰緛
                           鈹?                    鈹屸攢鈹€鈹€鈹€鈹€鈹€鈻尖攢鈹€鈹€鈹€鈹€鈹€鈹€鈹?    鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?                    鈹? Flask 鍚庣   鈹傗攢鈹€鈹€鈹€鈫掆攤  RAG 妫€绱?    鈹?                    鈹? 宸ヨ壓鐢熸垚绠＄嚎  鈹?    鈹? 鐭ヨ瘑搴撳尮閰?   鈹?                    鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹?    鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?                           鈹?                    SSE 娴佸紡鎺ㄩ€?鈹?宸ヨ壓瑙勭▼鏂囨湰
                           鈹?                    鈹屸攢鈹€鈹€鈹€鈹€鈹€鈻尖攢鈹€鈹€鈹€鈹€鈹€鈹€鈹?                    鈹? 鎵撳瓧鏈哄紩鎿?  鈹?                    鈹? 閫愯鍔ㄧ敾杈撳嚭  鈹?                    鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹?                           鈹?                    鈹屸攢鈹€鈹€鈹€鈹€鈹€鈻尖攢鈹€鈹€鈹€鈹€鈹€鈹€鈹?                    鈹? 宸ヨ壓瑙勭▼闈㈡澘  鈹?鈫?鐢ㄦ埛缂栬緫/瀵煎嚭
                    鈹? contenteditable 鈹?                    鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?```

---

## 鍚姩鏂瑰紡

### 涓€閿惎鍔紙鎺ㄨ崘锛?
```bat
start_flask_demo.bat
```

鑴氭湰鑷姩妫€娴?Python 鐜锛坄.venv` > `py` > `python`锛夛紝閲婃斁 5190 绔彛锛屽惎鍔ㄥ悗绔紝绛夊緟鍋ュ悍妫€鏌ラ€氳繃鍚庢墦寮€娴忚鍣ㄣ€?
### 鎵嬪姩鍚姩

```bash
# 1. 鍚姩鍚庣
cd F:\Work_Dir\2D-v
python -m backend.run

# 2. 娴忚鍣ㄦ墦寮€
# http://localhost:5190/dev/demo-industrial-console
```

### 鍋滄

```bat
stop_flask_demo.bat
```

---

## 璁捐绯荤粺

- **閰嶈壊锛?* 钃濊壊鍝佺墝鑹诧紙`#1a56db`锛夈€佹鑹插己璋冭壊锛坄#ff6528`锛夈€佽涔夎壊锛堢豢/榛?绾級
- **鍦嗚锛?* 澶у崱鐗?18-20px锛屽皬鍏冪礌 10-12px锛岃嵂涓?999px
- **瀛椾綋锛?* PingFang SC / Microsoft YaHei锛岀瓑瀹戒娇鐢?Cascadia Code / Fira Code
- **鍔ㄧ敾锛?* 鎸夐挳鍏夋辰鎵繃锛坄button-sheen`锛夈€佽繘搴︽潯鍛煎惛锛坄workflow-pulse`锛夈€佽鍏ュ満锛坄processRowIn`锛夈€佹墦瀛楀厜鏍囬棯鐑侊紙`cursorBlink`锛?- **鍝嶅簲寮忥細** 1260px 鏂偣鎶樺彔缃戞牸甯冨眬锛?80px 鏂偣闅愯棌渚ф爮
- **鏃犻殰纰嶏細** `skip-link`銆乣focus-visible` 鏍峰紡銆乣aria-live` 鍖哄煙銆乣aria-expanded` 鐘舵€?
