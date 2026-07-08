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
- *Thua-còn-cứu-được*: khách còn ngày khác trong tuần, bị đẩy lùi 1 bước hôm nay
  không sao, ngày mai vẫn thử lại được.
- *Thua-là-mất-luôn*: khách mà **hôm nay là ngày cuối cùng** họ còn window trong
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

| Chỉ số | Gốc (292) | Sau fix (298) |
|---|---|---|
| Completion rate | 97.33% | 99.33% |
| Không hoàn thành | 8 | 2 |
| Tổng quãng đường | 1620.9 km | 1660.9 km |
| Tổng thời gian chờ | 4140.1 phút | 4106.7 phút |
| Độ lệch chuẩn giờ-về | 3.67h | 3.13h |

Verify bằng `verify.py` (kiểm tra độc lập, không dùng lại logic của scheduler): pass,
không vi phạm time-window, không giao trùng, không vượt 24h. Ổn định qua nhiều lần
chạy lặp lại (kết quả deterministic — `csv.DictReader` giữ nguyên thứ tự dòng trong
CSV nên `dict(customers)` không phụ thuộc hash-randomization).

### Giới hạn còn lại — ca C095/C268 ở ngày 5

Sau khi áp dụng cơ chế trên, còn đúng 2 khách unfulfilled: **C095** (window ngày 4,
5) và **C268** (window ngày 1, 5). Trace cho thấy:

- Ngày 5 dồn tới **15 candidate last-chance cùng lúc** (nhiều tuần "hết hạn" đổ dồn
  vào cuối tuần).
- Ngay trong nội bộ Giai đoạn 1 (route trống, cạnh tranh công bằng), Cheapest
  Insertion chỉ chèn được 13/15 người — C095 và C268 thua nhau (và thua các candidate
  last-chance khác) trong chính nhóm được ưu tiên tuyệt đối.

Đây là giới hạn vật lý thật của khung giờ hẹp, không phải điểm có thể vá thêm bằng
cách đổi thứ tự xử lý — đã thử cả xen kẽ 2-opt/Or-opt giữa mỗi lần chèn last-chance
(để mở thêm khe hở) và đổi thứ tự ưu tiên trong nhóm last-chance, không cải thiện
được thêm.

### Lưu ý về đánh đổi

Giai đoạn 1 chỉ ưu tiên last-chance-**của-hôm-nay**; nó không đảm bảo tối ưu toàn
cục cho những khách sắp thành last-chance vào 1–2 ngày tới. Có 1 ca ghi nhận được:
khách **C095** vốn được giao thành công ở ngày 4 trong một biến thể thử nghiệm khác
(ưu tiên tuyệt đối, không giữ EDF làm tie-break) — nhưng ngày 5 (last-chance thật của
nó) vẫn thua sát nút trong nhóm 15 người. Điều này không làm giảm completion rate
tổng (kết quả cuối vẫn 298), nhưng là lời nhắc rằng cơ chế "giữ chỗ theo ngày" có thể
đổi *ai* được cứu, không chỉ *có bao nhiêu* người được cứu.
