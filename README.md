# Transportation_optimization

Lời giải cho đề thi **Vòng Sơ loại — Bảng B, Cuộc thi Toán Mô hình 2026**: *"Ứng dụng Toán học trong thiết kế lộ trình giao hàng tối ưu"*.

Bài toán là một biến thể của **VRPTW (Vehicle Routing Problem with Time Windows)** cho **một xe duy nhất**, trải trên **7 ngày trong tuần** (rolling horizon): mỗi khách hàng có một hoặc nhiều khung giờ nhận hàng khác nhau tùy ngày; nếu không giao được hôm nay, đơn có thể được hẹn sang các ngày sau trong cùng tuần; đến Chủ Nhật mà vẫn chưa giao thì đơn đó tính là **không hoàn thành**.

Repo này cài đặt:
- Thuật toán chính: **Cheapest Insertion + EDF (Earliest Deadline First) liên ngày**, có thêm **multi-start last-chance reservation** và hậu xử lý bằng **Local Search (2-opt + Or-opt)**.
- Hai phương án cơ sở (baseline) để so sánh định lượng: **Nearest Neighbor** và **Minimize Deferral**.
- Bộ chỉ số đánh giá chất lượng lịch giao hàng (`metrics.py`) và một trình kiểm định độc lập (`verify.py`) để đảm bảo lời giải luôn hợp lệ.
- Xuất kết quả ra CSV chi tiết và một bản đồ HTML tương tác (Plotly) để trực quan hóa lộ trình từng ngày.

Trên bộ dữ liệu chính thức của đề bài (300 khách hàng, `Data/locations.csv` + `Data/time_windows.csv`), thuật toán chính đạt **100% completion rate (300/300)**.

---

## Mục lục

- [Cấu trúc thư mục (Project Structure)](#cấu-trúc-thư-mục-project-structure)
- [Cài đặt](#cài-đặt)
- [Cách chạy](#cách-chạy)
- [Luồng xử lý (Pipeline)](#luồng-xử-lý-pipeline)
- [Thuật toán chính](#thuật-toán-chính)
- [Baselines](#baselines)
- [Bộ chỉ số đánh giá (Metrics)](#bộ-chỉ-số-đánh-giá-metrics)
- [Dữ liệu đầu vào](#dữ-liệu-đầu-vào)
- [Kết quả đầu ra](#kết-quả-đầu-ra)
- [Tài liệu phân tích thêm](#tài-liệu-phân-tích-thêm)
- [Lưu ý kỹ thuật](#lưu-ý-kỹ-thuật)

---

## Cấu trúc thư mục (Project Structure)

```
Transportation_optimization/
│
├── main.py                          # Entry point CLI: chọn dataset -> chạy scheduler -> xuất HTML + CSV -> in metrics
│
├── main_algorithm/                  # Lõi thuật toán
│   ├── data_model.py                #   Đọc CSV, định nghĩa Customer/TimeWindow, ma trận khoảng cách & thời gian di chuyển
│   ├── scheduler.py                 #   Cheapest Insertion + EDF liên ngày, multi-start last-chance, rolling horizon 7 ngày
│   └── local_search.py              #   Hậu xử lý route: 2-opt (gỡ chéo) + Or-opt (dời điểm kẹt)
│
├── test_algorithm/                  # Baselines, đo lường chất lượng, kiểm định
│   ├── baselines.py                 #   Baseline 1 (Nearest Neighbor) & Baseline 2 (Minimize Deferral)
│   ├── metrics.py                   #   Tính 5 chỉ số chất lượng lịch giao hàng (WeeklyMetrics)
│   ├── verify.py                    #   Kiểm định độc lập tính hợp lệ của lời giải (feasibility checker)
│   ├── make_charts.py               #   Script sinh biểu đồ so sánh thuật toán chính vs. baselines (PNG)
│   └── make_chart_local_search.py   #   Script sinh biểu đồ so sánh trước/sau khi thêm Local Search (PNG)
│
├── gen_output/                      # Xuất kết quả
│   ├── exporter.py                  #   Xuất WeeklyResult ra CSV (chi tiết route, khách bị hoãn, khách không hoàn thành)
│   └── weekly_route.py              #   Vẽ bản đồ tương tác HTML (Plotly) theo từng ngày trong tuần
│
├── Data/                            # Dữ liệu đầu vào
│   ├── locations.csv                #   Bộ dữ liệu CHÍNH THỨC của đề bài — 300 khách hàng + 1 depot
│   ├── time_windows.csv             #   Khung giờ nhận hàng tương ứng với locations.csv
│   ├── locations_new.csv            #   Bộ dữ liệu mở rộng để test thêm — 600 khách hàng + 1 depot
│   ├── time_window_new.csv          #   Khung giờ nhận hàng tương ứng với locations_new.csv
│   └── EDA_TMH2026_BangB.ipynb      #   Notebook phân tích khám phá dữ liệu (EDA) trước khi thiết kế thuật toán
│
├── Output/                          # Kết quả đã chạy sẵn (mỗi cặp *_new / *_old ứng với 1 trong 2 bộ dữ liệu ở trên)
│   ├── output_new.csv / output_old.csv                          # Chi tiết từng điểm dừng trong tuần
│   ├── delayed_customers_new.csv / delayed_customers_old.csv    # Khách bị hoãn theo từng ngày + ngày giao thực tế dự kiến
│   ├── unfulfilled_customers_new.csv / unfulfilled_customers_old.csv  # Khách không giao được trong cả tuần
│   └── weekly_routes_new.html / weekly_routes_old.html          # Bản đồ tương tác 7 ngày (mở bằng trình duyệt)
│
├── analysis_source/                 # Tài liệu phân tích kỹ thuật nội bộ (giải thích sâu code + quyết định thiết kế)
│   ├── 01_overall_pipeline_and_structures.md   # Kiến trúc tổng thể & cấu trúc dữ liệu
│   ├── 02_cheapest_insertion_and_edf.md        # Mổ xẻ chi tiết scheduler.py
│   ├── 02_2_main_agolorithm.md                 # Kiến trúc thuật toán CHI-LS (góc nhìn khác, bổ sung)
│   ├── 03_baseline_strategies.md               # Phân tích các chiến lược baseline
│   ├── 04_metrics_and_verification.md          # Bộ chỉ số đánh giá & cơ chế kiểm định
│   ├── 05_complexity_analysis.md               # Đánh giá độ phức tạp thời gian/không gian
│   └── BUGFIX_NOTES.md                         # Nhật ký các quyết định thiết kế quan trọng, kèm ca cụ thể đã kiểm chứng
│
├── .gitignore
└── README.md
```

---

## Cài đặt

Yêu cầu Python ≥ 3.9 (code dùng cú pháp generic built-in như `list[str]`).

Các thư viện ngoài cần cài:

```bash
pip install pandas matplotlib plotly seaborn numpy
```

- `pandas` — bắt buộc, dùng để xuất CSV (`gen_output/exporter.py`).
- `plotly` — bắt buộc, dùng để vẽ bản đồ tương tác HTML (`gen_output/weekly_route.py`).
- `matplotlib` — dùng cho các script vẽ chart PNG trong `test_algorithm/` (`make_charts.py`, `make_chart_local_search.py`).
- `seaborn`, `numpy` — chỉ dùng trong notebook EDA (`Data/EDA_TMH2026_BangB.ipynb`).

---

## Cách chạy

### Chạy pipeline đầy đủ (khuyến nghị)

Từ thư mục gốc của repo:

```bash
python main.py
```

Chương trình sẽ hỏi lần lượt qua 3 menu tương tác trên terminal:

1. **Chọn dataset** — Dataset mới (`locations_new.csv` + `time_window_new.csv`, 600 khách) / Dataset cũ (`locations.csv` + `time_windows.csv`, 300 khách — **bộ chính thức của đề bài**) / hoặc tự nhập đường dẫn khác.
2. **Chọn nơi lưu CSV output** — dùng tên mặc định (`*_new`/`*_old`) hoặc tự đặt tên.
3. **Chọn nơi lưu HTML output** — tương tự.

Sau đó chương trình sẽ tự động: load dữ liệu → chạy `weekly_scheduler_with_local_search` → sinh bản đồ HTML tương tác (tự mở trình duyệt) → xuất 3 file CSV → in ra bộ chỉ số đánh giá (`WeeklyMetrics`) ra terminal.

### Chạy từng module riêng lẻ (để debug / thử nghiệm)

Mỗi file trong `main_algorithm/` và `test_algorithm/` đều có khối `if __name__ == "__main__":` để chạy độc lập, ví dụ:

```bash
# Chạy thẳng thuật toán chính trên bộ dữ liệu chính thức, in kết quả ra terminal
python -m main_algorithm.scheduler

# Chạy 2 baseline và so sánh nhanh
python -m test_algorithm.baselines

# Kiểm định độc lập tính hợp lệ của lời giải
python -m test_algorithm.verify

# Tính & in bộ chỉ số đánh giá cho thuật toán chính lẫn baseline
python -m test_algorithm.metrics
```

Vì các module dùng import dạng `from main_algorithm.scheduler import ...`, nên cần chạy bằng cờ `-m` (hoặc chạy từ thư mục gốc repo) để Python nhận đúng package, thay vì `python main_algorithm/scheduler.py` trực tiếp.

---

## Luồng xử lý (Pipeline)

```
Data CSV (locations + time_windows)
        │
        ▼
data_model.load_data()  ──►  Customer objects + TimeWindow theo từng ngày (1=Thứ Hai .. 7=Chủ Nhật)
        │
        ▼
scheduler.weekly_scheduler_with_local_search()   [Rolling Horizon: Ngày 1 -> Ngày 7]
        │
        │  Với mỗi ngày:
        ├─ 1) Lọc candidates = khách đang pending & có window đúng ngày hôm nay
        ├─ 2) Tách "last-chance" (hôm nay là ngày cuối họ còn window trong tuần)
        │      khỏi "normal" (còn ngày dự phòng khác trong tuần)
        ├─ 3) Giai đoạn 1: xây route CHỈ với last-chance bằng Cheapest Insertion multi-start
        ├─ 4) Giai đoạn 2: lấp normal candidates vào phần route còn lại (EDF + Cheapest Insertion)
        ├─ 5) Giai đoạn 3: improve_route() — 2-opt + Or-opt (chỉ đổi thứ tự, không đổi ai được giao)
        └─ 6) Khách không chèn được hôm nay -> ở lại hàng đợi `pending`, tự động xét lại ngày sau
        │
        ▼
Hết ngày 7: khách còn lại trong `pending` -> WeeklyResult.unfulfilled
        │
        ├──► gen_output.weekly_route.plot_weekly_routes_interactive()  ──► HTML bản đồ tương tác
        ├──► gen_output.exporter.*_to_csv()                            ──► 3 file CSV
        └──► test_algorithm.metrics.compute_metrics() + print_metrics() ──► WeeklyMetrics in ra terminal
```

---

## Thuật toán chính

Cài đặt trong `main_algorithm/scheduler.py`, hàm `weekly_scheduler_with_local_search()`.

**Ý tưởng cốt lõi:** kết hợp **Cheapest Insertion Heuristic** (Solomon, 1987) — mỗi bước chèn khách vào vị trí trong route sao cho phát sinh ít chi phí (quãng đường + thời gian chờ) nhất — với **EDF (Earliest Deadline First)** để quyết định khách nào được ưu tiên xét trước trong ngày, dựa trên "deadline" ước lượng = khung giờ kết thúc sớm nhất còn khả dụng của khách trong cả tuần.

Ba điểm cải tiến so với Cheapest Insertion + EDF thuần túy:

1. **Tách last-chance khỏi normal candidates mỗi ngày.** Với Cheapest Insertion thuần, khi 2 khách có chi phí chèn gần bằng nhau, người thua chỉ đơn giản bị đẩy sang bước sau — vô hại nếu họ còn ngày khác trong tuần, nhưng **thua là mất vĩnh viễn** nếu hôm nay đã là ngày cuối cùng họ còn window. Thuật toán xây route cho nhóm last-chance TRƯỚC (route còn trống, cạnh tranh công bằng), rồi mới lấp nhóm normal vào phần còn lại.
2. **Multi-start cho nhóm last-chance** (`day_route_cheapest_insertion_multistart`). Vì Cheapest Insertion là greedy thuần, thứ tự duyệt candidate ở bước đầu (vốn chỉ phụ thuộc thứ tự đọc CSV) có thể khiến một vài last-chance bị thua oan dù bài toán vẫn còn đủ chỗ với thứ tự khác. Hàm này thử lần lượt từng candidate làm người được "ép chèn trước", giữ lại kết quả có completion cao nhất.
3. **Local Search hậu xử lý** (`local_search.py`): sau khi route trong ngày đã chèn xong, chạy xen kẽ **2-opt** (gỡ các đoạn đường cắt chéo nhau) và **Or-opt** (dời một đoạn ngắn 1–3 điểm bị "kẹt" sang vị trí khác) để giảm `return_time`, mà **không** thêm/bớt khách nào khỏi route — đảm bảo completion rate không bị ảnh hưởng.

Xếp hạng chèn dùng `local_insertion_cost` (chi phí cục bộ tại đúng chỗ chèn: quãng đường tăng thêm + thời gian chờ phát sinh của riêng khách mới) thay vì thay đổi `return_time` toàn route, để tránh "phạt oan" các phép chèn-giữa khi route đã đông khách (chi tiết lý do trong `analysis_source/BUGFIX_NOTES.md`).

Ràng buộc cứng được kiểm tra ở mọi bước chèn: xe phải về kho trước 24:00 (`DAY_END_MINUTE = 1440` phút) và thời điểm bắt đầu phục vụ phải nằm trong một khung giờ hợp lệ của khách (nếu đến sớm hơn thì phải chờ).

---

## Baselines

Cài đặt trong `test_algorithm/baselines.py`, cả hai đều chạy trong cùng khung rolling-horizon 7 ngày như thuật toán chính để đảm bảo so sánh công bằng:

| Baseline | Ý tưởng | Hàm |
|---|---|---|
| **1. Nearest Neighbor** | Mỗi bước luôn nối đuôi vào cuối route khách **chưa giao gần vị trí hiện tại nhất** (khoảng cách Euclid) mà vẫn khả thi. | `day_route_nearest_neighbor` |
| **2. Minimize Deferral** | Chia candidate mỗi ngày thành Nhóm A ("đến hạn" — hôm nay chính là ngày sớm nhất khách có thể được giao) và Nhóm B ("quá hạn" — đã trễ hạn từ trước). Ưu tiên tuyệt đối Nhóm A bằng Cheapest Insertion multi-start, sau đó mới lấp Nhóm B. Bám sát đúng công thức `deferral_rate` dùng trong `metrics.py`. | `day_route_minimize_deferral` |

Cả hai baseline đều **không** có bước Local Search (2-opt/Or-opt) — dừng lại ở route thô sau khi chèn xong, đúng vai trò của một baseline để làm mốc so sánh.

---

## Bộ chỉ số đánh giá (Metrics)

Cài đặt trong `test_algorithm/metrics.py`, hàm `compute_metrics()`. Gồm 5 chỉ số, **xếp theo thứ tự ưu tiên** dùng trong báo cáo:

| # | Chỉ số | Ý nghĩa | Mức ưu tiên |
|---|---|---|---|
| 1 | **Completion Rate (%)** | Tỉ lệ đơn giao thành công trong tuần | Cao nhất — một đơn không giao được là hậu quả nghiêm trọng nhất (mất đơn, mất uy tín) |
| 2 | **Total Travel Distance (km)** | Tổng quãng đường xe chạy cả tuần | Thứ hai — phản ánh trực tiếp chi phí vận hành |
| 3 | **Total Waiting Time (phút)** | Tổng thời gian xe đứng chờ vì đến sớm hơn window | Thứ ba — thời gian "chết" nhưng ít tốn kém hơn quãng đường |
| 4 | **Route Duration Balance** (độ lệch chuẩn giờ-về-kho giữa các ngày) | Mức cân bằng khối lượng công việc giữa các ngày trong tuần | Thứ tư — đo tính bền vững cho tài xế |
| 5 | **Deferral Rate (%)** | Tỉ lệ đơn phải hẹn lại sang ngày khác thay vì giao ngay ngày sớm nhất có thể | Chỉ số tham khảo — hẹn lại đôi khi là đánh đổi hợp lý để tối ưu tổng thể |

`test_algorithm/verify.py` đóng vai trò kiểm định độc lập: kiểm tra lại từ đầu mọi ràng buộc (đúng time window, đến-chờ-phục vụ đúng công thức, về kho trước 24h, không giao trùng khách, `served ∪ unfulfilled` khớp đúng danh sách khách gốc) để đảm bảo `WeeklyResult` do thuật toán trả về luôn hợp lệ.

---

## Dữ liệu đầu vào

Hai file CSV theo đúng định dạng đề bài quy định:

**`locations.csv`** — thông tin kho & khách hàng:

| Cột | Ý nghĩa |
|---|---|
| `location_id` | Mã địa điểm (`DEPOT` cho kho trung tâm, `C001`, `C002`, ... cho khách hàng) |
| `location_name` | Tên địa điểm |
| `x_km`, `y_km` | Tọa độ (đơn vị km) |
| `demand_kg` | Khối lượng hàng cần giao (kg) |
| `service_time` | Thời gian phục vụ tại điểm đó (phút) |

**`time_windows.csv`** — khung giờ nhận hàng của từng khách theo từng ngày:

| Cột | Ý nghĩa |
|---|---|
| `location_id` | Mã khách hàng |
| `day_of_week` | 1 = Thứ Hai, ..., 7 = Chủ Nhật |
| `start_time`, `end_time` | Khung giờ nhận hàng, định dạng `HH:MM` |

Một khách có thể có **nhiều dòng** (nhiều khung giờ trong cùng một ngày, hoặc khung giờ khác nhau ở các ngày khác nhau); cũng có thể **không có dòng nào** cho một ngày cụ thể (nghĩa là ngày đó khách không nhận hàng).

Thời gian di chuyển giữa 2 điểm được tính từ khoảng cách Euclid với vận tốc cố định **50 km/h** (tốc độ tối đa cho phép theo đề bài — thuật toán giả định xe luôn chạy đúng tốc độ này để có một ước lượng thời gian xác định, không mô hình hóa tắc đường).

Repo có sẵn 2 cặp dữ liệu trong `Data/`:
- `locations.csv` + `time_windows.csv` — **bộ dữ liệu chính thức** của đề thi (300 khách hàng).
- `locations_new.csv` + `time_window_new.csv` — bộ dữ liệu mở rộng tự tạo thêm để kiểm thử ở quy mô lớn hơn (600 khách hàng).

`Data/EDA_TMH2026_BangB.ipynb` là notebook phân tích khám phá dữ liệu (phân bố tọa độ, số lượng/độ dài khung giờ, missing values, v.v.) được thực hiện trước khi thiết kế thuật toán, để các quyết định thiết kế (như tách last-chance, EDF theo ngày) có căn cứ từ đặc điểm thật của dữ liệu chứ không phải đoán mò.

---

## Kết quả đầu ra

Chạy `main.py` (hoặc gọi trực tiếp các hàm trong `gen_output/`) sẽ tạo ra:

1. **`output_*.csv`** — chi tiết từng điểm dừng trong tuần: ngày, mã khách, demand, service_time, tọa độ, khung giờ đã dùng, thời điểm bắt đầu/kết thúc phục vụ, quãng đường tích lũy trong ngày. Bao gồm cả dòng xuất phát và dòng quay về kho mỗi ngày.
2. **`delayed_customers_*.csv`** — danh sách khách có window vào một ngày cụ thể nhưng **không** được giao đúng ngày đó, kèm `expected_day` (ngày họ thực sự được giao sau cùng, hoặc `0` nếu không giao được cả tuần).
3. **`unfulfilled_customers_*.csv`** — lọc lại từ file trên, chỉ giữ khách **chắc chắn không giao được** trong suốt cả tuần (trên bộ dữ liệu chính thức, file này rỗng — completion rate 100%).
4. **`weekly_routes_*.html`** — bản đồ tương tác Plotly, chia lưới 2×4 (7 ngày + 1 ô trống), mỗi ô thể hiện lộ trình trong ngày đó với chú giải màu:
   - 🔵 xanh dương — khách được giao hôm nay
   - ⚪ xám — khách chờ giao vào ngày sau (còn cơ hội)
   - 🟠 vàng/cam — "last-chance": hôm nay là ngày cuối họ còn window trong tuần
   - 🔴 đỏ — khách sẽ rớt đơn cả tuần (chưa tới ngày cuối cùng của họ)
   - 🟥 vuông đỏ — kho trung tâm

Cả 2 bộ kết quả (`*_new` cho 600 khách, `*_old` cho 300 khách bộ chính thức) đã được chạy sẵn và có mặt trong `Output/` để tham khảo mà không cần chạy lại.

---

## Tài liệu phân tích thêm

Thư mục `analysis_source/` chứa các ghi chú kỹ thuật đi sâu vào từng phần của code, hữu ích khi cần hiểu **tại sao** một quyết định thiết kế được chọn (không chỉ đọc code mà còn hiểu lý do), đặc biệt:

- **`BUGFIX_NOTES.md`** — nhật ký các quyết định thiết kế quan trọng nhất (vì sao xếp hạng chèn dùng `local_insertion_cost` thay vì `new_return_time`, vì sao cần multi-start cho last-chance...), kèm số liệu/ca cụ thể đã trace thủ công trên bộ dữ liệu thật.
- **`05_complexity_analysis.md`** — đánh giá độ phức tạp thời gian/không gian lý thuyết và thực tế của thuật toán chính lẫn các baseline.

---

## Lưu ý kỹ thuật

- Đơn vị thời gian nội bộ toàn bộ hệ thống là **phút tính từ 00:00 của ngày trong tuần đang xét** (mỗi ngày reset lại từ 0, không cộng dồn qua nhiều ngày, vì xe luôn xuất phát lại từ kho mỗi sáng).
- `local_search.py` import `Stop`, `DayRoute` từ `scheduler.py`, còn `scheduler.py` phải import `improve_route` từ `local_search.py` một cách **trễ (deferred import, bên trong hàm)** để tránh circular import giữa 2 module.
- Đường dẫn dữ liệu trong các khối `if __name__ == "__main__":` của từng file được viết dạng tương đối (ví dụ `"Data/locations.csv"`), nên khi chạy độc lập một module cần đứng ở **thư mục gốc của repo**.
