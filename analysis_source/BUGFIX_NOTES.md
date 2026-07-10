# BUGFIX_NOTES.md

Ghi chú kỹ thuật cho các quyết định thiết kế trong `scheduler.py` mà docstring có
trỏ tới file này. Mục đích: giải thích **tại sao** code hiện tại làm như vậy, kèm
số liệu/ca cụ thể đã kiểm chứng, để không phải đoán lại khi đọc code sau này.

---

## 1. Xếp hạng ứng viên chèn: `local_insertion_cost`, không phải `new_return_time`

**Vị trí liên quan:** `try_insert_at_position()`, dòng ~74–121.

### Vấn đề

Khi Cheapest Insertion so sánh nhiều ứng viên (khách, vị trí) để chọn phép chèn "rẻ
nhất", có hai cách đo chi phí khả dĩ:

- **`new_return_time`** — thời điểm về kho MỚI của toàn bộ route sau khi chèn.
- **`local_insertion_cost`** — chi phí CỤC BỘ chỉ của riêng phép chèn đó: phần quãng
  đường/thời gian tăng thêm tại đúng chỗ chèn, cộng waiting-time phát sinh của riêng
  khách mới, KHÔNG cộng dồn phần waiting-time bị dịch chuyển dây chuyền của các điểm
  phía sau vị trí chèn.

Dùng `new_return_time` để xếp hạng có vấn đề: nếu route đã đông, chèn vào **giữa**
route sẽ đẩy lùi arrival của mọi điểm phía sau, có thể làm họ phải chờ lâu hơn tại
time-window của chính họ (không phải lỗi của phép chèn, mà do cấu trúc route sẵn
có) — khoản chờ dây chuyền này bị cộng gộp vào `new_return_time` một cách không công
bằng, khiến chèn-giữa bị "phạt oan" so với chèn-cuối, dù về bản chất phép chèn giữa
có thể rẻ hơn nhiều tại đúng vị trí đó.

### Fix

`local_insertion_cost` = `detour + own_waiting`, trong đó:

- `detour = travel(prev, new) + travel(new, next) − travel(prev, next)` (chỉ tính
  phần tăng thêm tại chỗ chèn; nếu chèn cuối route thì không có phần trừ vì không có
  "next").
- `own_waiting` = thời gian riêng khách mới phải chờ đến `window.start`, nếu đến sớm.

Đây là định nghĩa chuẩn của "Cheapest Insertion Cost" trong y văn VRPTW (Solomon,
1987). `new_return_time` vẫn được trả về và dùng để **kiểm tra khả thi** (≤ 24h),
nhưng không dùng để xếp hạng ứng viên.

---

## 2. Last-chance reserve — cơ chế đưa completion rate từ 292 lên 298

**Vị trí liên quan:** `weekly_scheduler_with_local_search()`, dòng ~288–411.

### Hiện tượng quan sát được

8 khách bị rớt đơn ở bản gốc (`weekly_scheduler`, Cheapest Insertion + EDF thuần)
đều có window trùng nhau: **18:30–21:30 (3 tiếng)**. Đếm candidate mỗi ngày cho thấy
~74–81 khách/ngày (ngày 1–5) đều muốn đúng khung giờ này, nhưng route mỗi ngày chỉ
chèn được ~19–25 người vào khung đó — cầu vượt cung rõ rệt (capacity bottleneck thật
sự của bài toán, không phải lỗi thuật toán).

### Nguyên nhân sâu hơn — không chỉ là "hết chỗ"

Trace thủ công từng bước Cheapest Insertion cho route ngày 4 (dùng lại đúng trạng
thái `pending` sau khi ngày 1–3 đã chạy), phát hiện:

- Tại bước route đã có 24 điểm, ứng viên **C267** được chọn với `local_insertion_cost
= 18.203`.
- Ngay tại bước đó, ứng viên **C278** (khách sau này bị unfulfilled ở bản gốc) cũng
  khả thi, với `local_insertion_cost = 18.349` — chênh lệch **0.146**, chưa tới 1%.
- C278 thua sát nút, bị đẩy sang vòng lặp kế tiếp. Nhưng ở vòng sau, route tiếp tục
  phát triển sang một cụm không gian khác (qua C207 và các điểm cách đó 13–17km).
  Từ đó, C278 không còn khả thi ở bất kỳ vị trí nào trong route ngày 4 nữa — dù vị
  trí nó đứng chỉ cách route (qua C267) đúng **0.1km**.
- Verify thủ công: chèn C278 ngay sau C267 (thời điểm C267 vừa được chọn) hoàn toàn
  khả thi, chỉ tốn thêm ~7 phút detour trên toàn tuyến, route vẫn còn dư ~117 phút
  tới giới hạn 24h.

**Kết luận:** Cheapest Insertion không phân biệt được hai loại "thua" khác nhau:

- _Thua-còn-cứu-được_: khách còn ngày khác trong tuần, bị đẩy lùi 1 bước hôm nay
  không sao, ngày mai vẫn thử lại được.
- _Thua-là-mất-luôn_: khách mà **hôm nay là ngày cuối cùng** họ còn window trong
  tuần — bị đẩy lùi dù chỉ 1 bước là fail vĩnh viễn, vì route sau đó "đi xa" và
  không quay lại nữa.

Vì thuật toán chỉ nhìn chi phí cục bộ tại từng bước, nó không biết khách nào thuộc
loại nào — nên xử lý cả hai như nhau, và ngẫu nhiên để mất một số khách thuộc loại
thứ hai dù chênh lệch chi phí lúc thua là không đáng kể.

### Cơ chế fix: hai giai đoạn mỗi ngày

1. **Giai đoạn 1 — giữ chỗ:** Tách các candidate mà `next_available_day(cust, day)`
   trả về `None` (không còn ngày nào khác trong tuần). Xây route Cheapest Insertion
   **chỉ với nhóm này**, trên route còn trống hoàn toàn. Vì route trống, họ cạnh
   tranh công bằng với NHAU (ai rẻ hơn thắng — vẫn đúng tinh thần Cheapest Insertion),
   thay vì luôn thua vì bị xét chung với toàn bộ candidate khác và bị đẩy lùi.

2. **Giai đoạn 2 — lấp chỗ còn lại:** Candidate còn ngày khác trong tuần được chèn
   vào phần route còn dư, theo đúng EDF + Cheapest Insertion như cũ. Nhóm này chịu
   thiệt khi bị từ chối — rolling horizon tự động xét lại họ vào ngày kế tiếp có
   window.

3. **Giai đoạn 3 — dọn route:** `improve_route()` (2-opt + Or-opt, `local_search.py`)
   chạy sau cùng, chỉ đổi thứ tự, không thêm/bớt ai.

### Kết quả đo được

| Chỉ số               | Gốc (292)   | Sau fix (298) |
| -------------------- | ----------- | ------------- |
| Completion rate      | 97.33%      | 99.33%        |
| Không hoàn thành     | 8           | 2             |
| Tổng quãng đường     | 1620.9 km   | 1660.9 km     |
| Tổng thời gian chờ   | 4140.1 phút | 4106.7 phút   |
| Độ lệch chuẩn giờ-về | 3.67h       | 3.13h         |

Verify bằng `verify.py` (kiểm tra độc lập, không dùng lại logic của scheduler): pass,
không vi phạm time-window, không giao trùng, không vượt 24h. Ổn định qua nhiều lần
chạy lặp lại (kết quả deterministic — `csv.DictReader` giữ nguyên thứ tự dòng trong
CSV nên `dict(customers)` không phụ thuộc hash-randomization).

### Giới hạn còn lại tại thời điểm này — ca C095/C268 ở ngày 5

> **Cập nhật:** giới hạn mô tả trong mục này đã được vượt qua bằng cơ chế multi-start
> ở mục 3 bên dưới (298 → 300). Giữ nguyên nội dung gốc dưới đây làm lịch sử trace,
> vì nó vẫn mô tả đúng nguyên nhân gốc rễ — mục 3 chỉ giải thích _tại sao_ kết luận
> "13/15 là trần vật lý" ở đây chưa đúng.

Sau khi áp dụng cơ chế trên, còn đúng 2 khách unfulfilled: **C095** (window ngày 4, 5) và **C268** (window ngày 1, 5). Trace cho thấy:

- Ngày 5 dồn tới **15 candidate last-chance cùng lúc** (nhiều tuần "hết hạn" đổ dồn
  vào cuối tuần).
- Ngay trong nội bộ Giai đoạn 1 (route trống, cạnh tranh công bằng), Cheapest
  Insertion chỉ chèn được 13/15 người — C095 và C268 thua nhau (và thua các candidate
  last-chance khác) trong chính nhóm được ưu tiên tuyệt đối.

Đây là giới hạn vật lý thật của khung giờ hẹp, không phải điểm có thể vá thêm bằng
cách đổi thứ tự xử lý — đã thử cả xen kẽ 2-opt/Or-opt giữa mỗi lần chèn last-chance
(để mở thêm khe hở) và đổi thứ tự ưu tiên trong nhóm last-chance, không cải thiện
được thêm.

> **Ghi chú (xem mục 3):** kết luận "13/15 là trần" ở trên hoá ra chỉ đúng với ĐÚNG
> một thứ tự chèn (thứ tự dict tự nhiên). "Đổi thứ tự ưu tiên trong nhóm last-chance"
> đã thử ở đây là đổi thứ tự XẾP HẠNG (EDF, demand...), không phải thử ép từng người
> làm điểm chèn đầu tiên rồi để phần còn lại cạnh tranh cheapest bình thường — hai
> cách "đổi thứ tự" này khác nhau, và chỉ cách thứ hai (multi-start) mới lộ ra trần
> thật là 14/15, không phải 13/15.

### Lưu ý về đánh đổi

Giai đoạn 1 chỉ ưu tiên last-chance-**của-hôm-nay**; nó không đảm bảo tối ưu toàn
cục cho những khách sắp thành last-chance vào 1–2 ngày tới. Có 1 ca ghi nhận được:
khách **C095** vốn được giao thành công ở ngày 4 trong một biến thể thử nghiệm khác
(ưu tiên tuyệt đối, không giữ EDF làm tie-break) — nhưng ngày 5 (last-chance thật của
nó) vẫn thua sát nút trong nhóm 15 người. Tại thời điểm viết mục này, điều đó không
làm giảm completion rate tổng (kết quả vẫn 298), nhưng là lời nhắc rằng cơ chế "giữ
chỗ theo ngày" có thể đổi _ai_ được cứu, không chỉ _có bao nhiêu_ người được cứu —
quan sát này về sau hoá ra chính là đầu mối dẫn tới mục 3 (nếu đổi được _ai_ được cứu
ở ngày 4, có thể đổi luôn _thành phần_ nhóm last-chance ngày 5, chứ không chỉ thứ tự
xử lý trong nội bộ ngày 5).

---

## 3. Multi-start cho Giai đoạn 1 — đưa completion rate từ 298 lên 300

**Vị trí liên quan:** `day_route_cheapest_insertion_multistart()` (hàm mới, dòng
~208–306), gọi từ `weekly_scheduler_with_local_search()` dòng ~473 (thay cho
`day_route_cheapest_insertion()` gốc, CHỈ ở Giai đoạn 1). `day_route_cheapest_insertion()`
gốc và toàn bộ `baselines.py` KHÔNG đổi.

### Vấn đề

Mục 2 kết luận 13/15 là "trần vật lý thật" cho nhóm last-chance ngày 5. Kết luận đó
đúng về mặt hiện tượng (route trống + Cheapest Insertion đúng thứ tự dict tự nhiên
= 13/15) nhưng SAI về mặt nguyên nhân: nó gán cho bài toán một giới hạn thực ra chỉ
là giới hạn của MỘT thứ tự chèn cụ thể.

Cheapest Insertion trong Giai đoạn 1 duyệt candidate theo `remaining.values()` —
tức thứ tự dict, tức thứ tự đọc dòng trong CSV, một thứ tự không mang ý nghĩa gì về
mặt bài toán. Khi 2 candidate có `local_insertion_cost` gần bằng nhau ở bước đầu
(route còn trống), người đứng trước trong dict luôn được chèn trước, dù chênh lệch
chi phí giữa họ có thể không đáng kể. Với candidate bình thường, thua một bước ở
đây không sao (mục 2 đã giải quyết việc đó bằng cách tách last-chance ra route
riêng). Nhưng ngay TRONG nội bộ nhóm last-chance, vấn đề y hệt vẫn xảy ra: ai đứng
trước trong dict vẫn có lợi thế hệ thống, và với last-chance, thua một bước là mất
luôn (không có "ngày mai" để thử lại).

### Kiểm chứng nguyên nhân

Lấy đúng nhóm 15 last-chance của ngày 5 (route đã chạy tới hết ngày 4 với code gốc
mục 2), thử ép từng người trong 15 người làm điểm chèn ĐẦU TIÊN (route trống nên chỉ
có 1 vị trí khả thi cho họ lúc đó — `pos=0`), rồi để 14 người còn lại cạnh tranh
cheapest-cạnh-tranh-công-bằng bình thường như Cheapest Insertion vẫn làm:

| Điểm khởi đầu bị ép                                   | Số người chèn được | Ai rớt                      |
| ----------------------------------------------------- | ------------------ | --------------------------- |
| C023, C098, C170, C171, C183, C250, C287, C296 (8/15) | 13/15              | luôn đúng C095 + C268       |
| C128 (1/15)                                           | 13/15              | C163 + C180 (khác cặp trên) |
| C076 (1/15)                                           | 14/15              | C095                        |
| C083, C095, C268 (3/15)                               | 14/15              | C076                        |
| C163, C180 (2/15)                                     | 14/15              | C268                        |

Không có điểm khởi đầu nào cho ra 15/15. Để loại trừ khả năng 15/15 tồn tại nhưng
"multi-start-ép-1-người" chưa đủ mạnh để tìm ra, chạy thêm 20.000 thứ tự chèn NGẪU
NHIÊN khác nhau cho đúng nhóm 15 người này (không chỉ ép người đầu tiên mà random
toàn bộ thứ tự, mỗi bước vẫn chèn theo vị trí rẻ nhất cho đúng người đang xét) — kết
quả: **chưa từng đạt 15/15 dù một lần**, trần luôn dừng ở 14/15.

**Kết luận:** trần vật lý thật của nhóm 15 last-chance ngày 5 (tại thời điểm route
đã cố định sau ngày 1–4 theo code gốc mục 2) là **14/15**, không phải 13/15. Con số
13/15 trong mục 2 là do THUA OAN vì thứ tự duyệt ngẫu nhiên (thứ tự CSV), không phải
vì bài toán chỉ cho phép 13.

### Fix

Thêm `day_route_cheapest_insertion_multistart()`: với n candidate trong nhóm
last-chance, thử LẦN LƯỢT từng candidate làm người bị ép chèn trước (route trống nên
chỉ có `pos=0`), để phần còn lại chạy ĐÚNG cơ chế cheapest-cạnh-tranh-công-bằng của
`day_route_cheapest_insertion()` gốc (không ưu tiên gì thêm từ bước 2 trở đi). Giữ
lại kết quả điểm khởi đầu nào có completion cao nhất; hoà completion thì lấy
`return_time` thấp hơn (đúng thứ tự ưu tiên completion > distance mà `metrics.py`
đã định nghĩa). Nếu người bị ép không chèn được ngay từ bước ép (hiếm — vd. hết
window ngay từ đầu), bỏ qua lượt start đó, không tính vào so sánh.

Chỉ thay lời gọi hàm ở Giai đoạn 1:

```python
route, unserved_last_chance = day_route_cheapest_insertion_multistart(
    last_chance, depot, all_points, day
)
```

Giai đoạn 2 và `baselines.py` giữ nguyên `day_route_cheapest_insertion()` gốc — nhóm
`normal_candidates` còn ngày dự phòng, thua hôm nay không mất hẳn, nên không cần trả
thêm chi phí tính toán multi-start cho họ; và baselines cần giữ nguyên hàm gốc để
việc so sánh 4 phương án trong report vẫn công bằng.

### Vì sao kết quả cuối là 300/300, không phải 299/300

Ước tính ban đầu (dựa riêng trên phân tích Giai đoạn 1 của ngày 5, giữ nguyên ngày
1–4 như code gốc mục 2) là 298 → 299 (chỉ cứu được 1 trong 2 người, vì trần là
14/15 chứ không phải 15/15). Nhưng multi-start áp dụng cho MỌI ngày có last-chance
(3–7), không chỉ ngày 5 — nên nó cũng cải thiện Giai đoạn 1 của ngày 4. Cụ thể:
khách **C128** (trước đây bị đẩy từ ngày 4 sang ngày 5 do thua ở Giai đoạn 1 ngày 4
theo code gốc mục 2) nay được chèn thành công NGAY Ở NGÀY 4. Hệ quả dây chuyền: nhóm
last-chance ngày 5 sau patch chỉ còn **14 người** (không phải 15, vì thiếu C128), và
với 14 người thì multi-start chèn đủ **14/14** — tức C095 VÀ C268 đều được cứu, thay
vì chỉ 1 trong 2 như ước tính ban đầu. Đây là ví dụ cụ thể cho đúng cảnh báo ở cuối
mục 2 ("Lưu ý về đánh đổi") — sửa _ai_ được cứu ở một ngày có thể đổi luôn _thành
phần_ nhóm last-chance của ngày sau, chứ không chỉ ai thắng ai thua trong nội bộ một
ngày cố định.

### Kết quả đo được

| Chỉ số                             | Trước (298, mục 2) | Sau (300, mục 3) |
| ---------------------------------- | ------------------ | ---------------- |
| Completion rate                    | 99.33%             | **100.00%**      |
| Không hoàn thành                   | 2 (C095, C268)     | **0**            |
| Tổng quãng đường thuần             | 1660.9 km          | 1626.5 km        |
| Tổng thời gian chờ                 | 4106.7 phút        | 4145.3 phút      |
| Độ lệch chuẩn giờ-về               | 3.13h              | 3.18h            |
| Thời gian chạy (7 ngày, 300 khách) | ~8.9s              | ~8.3s            |

Verify bằng `verify.py`: pass, không vi phạm time-window, không giao trùng, không
vượt 24h. Ổn định qua nhiều lần chạy lặp lại (cùng lý do determinism đã nêu ở mục 2).
`baselines.py` chạy độc lập cho kết quả y hệt trước patch (69.33% / 68.00% / 73.33%
completion cho 3 baseline) — xác nhận patch không rò rỉ ảnh hưởng sang phần code đó.

### Chi phí

Với n candidate trong nhóm last-chance, Giai đoạn 1 giờ chạy Cheapest Insertion đầy
đủ N lần (một lần cho mỗi điểm khởi đầu bị ép) thay vì 1 lần — chậm hơn ~N lần CHỈ
CHO RIÊNG bước xây route last-chance. Nhóm last-chance mỗi ngày trên bộ dữ liệu này
dao động ~10–23 người (nhỏ hơn nhiều so với 300 khách tổng), nên chi phí tuyệt đối
vẫn nhỏ: tổng thời gian chạy toàn pipeline không tăng so với trước (8.3s so với
8.9s — thực tế đo được còn nhanh hơn, nhiều khả năng do route ngắn hơn ở vài ngày
khiến `improve_route()` hội tụ nhanh hơn, chứ không phải multi-start miễn phí).

Nếu về sau nhóm last-chance có thể phình to hơn nhiều (vài trăm người/ngày), nên
cân nhắc giới hạn số điểm khởi đầu thử (vd. chỉ thử k candidate có
`local_insertion_cost` thấp nhất ở bước đầu, thay vì thử toàn bộ n người) để giữ chi
phí tuyến tính chứ không phình theo n.

### Giới hạn còn lại

Không còn khách nào unfulfilled (300/300). Vẫn cần lưu ý: multi-start chỉ áp dụng
cho Giai đoạn 1 (last-chance); nếu bộ dữ liệu tương lai lớn hơn hoặc cấu trúc window
khác đi, không có gì đảm bảo trần vật lý luôn trùng khớp với sức chứa thật — mục
này chỉ chứng minh với ĐÚNG bộ dữ liệu TMH2026 Bảng B hiện tại, 20.000 thứ tự chèn
ngẫu nhiên chưa từng vượt 14/15 cho nhóm cụ thể đó. Đây là bằng chứng thực nghiệm
mạnh, không phải chứng minh toán học rằng 14/15 là trần tuyệt đối cho MỌI cấu hình
15 candidate có thể có trong khung 18:30–21:30.
