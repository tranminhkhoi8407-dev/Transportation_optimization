# TÀI LIỆU KIẾN TRÚC THUẬT TOÁN ĐIỀU PHỐI TUYẾN ĐƯỜNG PHỨC HỢP
## CHI-LS (Cheapest Insertion with Local Search & Multi-Day Rolling Horizon)

Tài liệu kỹ thuật này mô tả chi tiết pipeline kiến trúc, mô hình toán học và tư duy tối ưu hóa của hệ thống lập lịch giao hàng tự động có ràng buộc cửa sổ thời gian cứng (VRPTW). Hệ thống được xây dựng trên sự kết hợp giữa chiến lược chèn tham lam cải tiến (Enhanced Cheapest Insertion) và các toán tử tìm kiếm cục bộ (Local Search Metaheuristic).

---

## 1. Tổng quan Kiến trúc và Pipeline Vận hành

Thuật toán hoạt động theo mô hình **Khung thời gian cuốn (Rolling Horizon)** dịch chuyển liên tục qua 7 ngày trong tuần (từ Thứ Hai đến Chủ Nhật). Tại mỗi ngày $d \in \{1, 2, ..., 7\}$, hệ thống khởi tạo một tuyến đường trống xuất phát từ Kho trung tâm (`depot`) và thực hiện một pipeline khép kín gồm 3 giai đoạn bổ trợ lẫn nhau:
```
+------------------------------------------------------------+
| Giai đoạn 1: Phân loại & Ưu tiên Ứng viên (Urgent vs Normal) |
+------------------------------------------------------------+
|
v
+------------------------------------------------------------+
| Giai đoạn 2: Xây dựng Tuyến đường (Enhanced Cheapest Insertion)|
|   - Đánh giá bằng Hàm Chi phí Cục bộ (Local Insertion Cost) |
+------------------------------------------------------------+
|
v
+------------------------------------------------------------+
| Giai đoạn 3: Hậu xử lý & Tối ưu hóa Hình học (Local Search) |
|   - 2-Opt (Gỡ rối giao cắt) & Or-Opt (Tái định vị điểm kẹt) |
|   - Đánh giá chất lượng bằng Tổng quãng đường (Distance)   |
+------------------------------------------------------------+
```
Mục tiêu cốt lõi của pipeline này là tối đa hóa **Tỷ lệ hoàn thành đơn hàng (Completion Rate)** trước, sau đó tối thiểu hóa **Tổng quãng đường di chuyển (Total Distance)** và **Thời gian chết (Waiting Time)**.

---

## 2. Giai đoạn 1: Phân loại & Quy tắc Lựa chọn Ứng viên (Candidate Selection)

Để bảo vệ chỉ số KPI tối cao là Tỷ lệ hoàn thành, thuật toán không xử lý danh sách khách hàng một cách cồng kềnh hay ngẫu nhiên. Trước khi bước vào vòng lặp chèn của ngày $d$, tập hợp khách hàng chưa được giao (`pending`) sẽ được quét và phân loại thành hai nhóm ưu tiên tuyệt đối:

### 2.1. Phân loại Nhóm Ứng viên
1. **Nhóm Cấp bách (Urgent / Last-chance Candidates):** Là những khách hàng có cửa sổ thời gian mở cửa vào ngày $d$, và ngày $d$ **là cơ hội cuối cùng trong tuần** của họ. Nếu ngày hôm nay xe không ghé qua, đơn hàng của họ chắc chắn sẽ bị hủy vĩnh viễn vĩnh viễn (Unfulfilled).
2. **Nhóm Thông thường (Normal Candidates):**
   Là những khách hàng có lịch mở cửa vào ngày $d$, nhưng trong các ngày tiếp theo ($d+1 \rightarrow 7$), họ vẫn còn ít nhất một ngày khác có thể tiếp nhận hàng.

### 2.2. Logic Vận hành và Tư duy Thiết kế
Thuật toán ép buộc hệ thống phải dồn toàn bộ tài nguyên thời gian và không gian đầu ngày để phục vụ nhóm `Urgent` trước, sau đó mới xét đến nhóm `Normal`. 

Tư duy thiết kế ở đây dựa trên nguyên lý **"Sắp xếp vật liệu"**: Khi một chiếc xô (tài nguyên ca làm việc 24 giờ) còn trống, độ linh hoạt về mặt thời gian và không gian là lớn nhất. Việc nhét những "viên đá lớn và góc cạnh" (đơn Urgent khó chiều) vào trước sẽ tận dụng được khoảng trống này. Các "viên cát" (đơn Normal linh hoạt) sẽ được đổ vào sau để lấp đầy các kẽ hở thời gian còn lại.

### 2.3. Nghịch lý "Bỏ rơi" đơn Urgent (Trade-offs & Ràng buộc cứng)
Ngay cả khi được đưa lên đầu hàng đợi xét duyệt với mức ưu tiên cao nhất, thuật toán **vẫn có thể bỏ lỡ và làm rớt các đơn Urgent**. Đây không phải lỗi logic, mà là giới hạn vật lý của bài toán tối ưu có ràng buộc cứng:
* **Xung đột cửa sổ thời gian:** Nếu hai khách hàng Urgent cùng yêu cầu giao hàng vào khung giờ hẹp (ví dụ: 08:00 - 09:00) nhưng nằm ở hai cực Nam - Bắc đối lập của bản đồ, xe chỉ có thể chọn một trong hai. Khách còn lại bắt buộc phải bị từ chối do không thể phân thân.
* **Giới hạn 24 giờ cứng (`DAY_END_MINUTE = 1440`):** Nếu một đơn Urgent nằm quá cô lập ở vùng biên bản đồ, thời gian di chuyển từ kho đến đó và quay về vượt quá quỹ thời gian cho phép của một ngày hoạt động, ràng buộc kiểm tra khả thi sẽ chém đứt phép chèn này để bảo vệ an toàn cho tài xế và phương tiện.

---

## 3. Giai đoạn 2: Quy trình Cheapest Insertion và Cơ chế Local Cost

Sau khi có danh sách ứng viên đã phân cấp, hệ thống tiến hành xây dựng lộ trình chi tiết. Thay vì nối đuôi vào cuối chặng một cách thô sơ, thuật toán duyệt qua từng vị trí chèn tiềm năng.

### 3.1. Sự thất bại của Heuristic `return_time` cũ
Trong phiên bản sơ khai, chi phí của một phép chèn được đánh giá dựa trên sự thay đổi của thời gian xe về kho: 
$$\Delta Return = T_{return\_new} - T_{return\_old}$$
Cơ chế này có một điểm mù chết người do hiện tượng **"Thời gian chùng" (Slack Time)** gây ra. Khi xe đi đường vòng tốn thêm nhiều km (lãng phí không gian), nhưng nếu đến điểm kế tiếp xe vẫn đến trước giờ mở cửa của khách hàng, xe sẽ phải tắt máy đứng chờ. Quãng thời gian chạy vòng vô ích đó đã hấp thụ hoàn toàn vào thời gian chờ đợi cũ. 

Kết quả là $T_{return\_new}$ không hề thay đổi so với $T_{return\_old}$ ($\Delta Return = 0$). Hệ thống lầm tưởng đó là một phép chèn miễn phí và chấp nhận nó, tạo ra các tuyến đường zig-zag thảm họa.

### 3.2. Hàm Chi phí Cục bộ Mới (Local Insertion Cost)
Để giải quyết triệt để điểm mù trên, thuật toán chuyển sang đánh giá chất lượng vị trí chèn dựa trên biến động cục bộ tại chính phân đoạn bị tác động. Khi thử chèn khách hàng $C$ vào giữa hai điểm dừng hiện tại là $A$ và $B$, chi phí được tính toán theo công thức phức hợp:

$$Cost(A, C, B) = \alpha \cdot \Delta Distance + \beta \cdot \Delta WaitTime + \gamma \cdot \Delta Delay$$

Trong đó:

#### 1. $\Delta Distance$ (Biến động Không gian hình học)
$$\Delta Distance = Dist(A, C) + Dist(C, B) - Dist(A, B)$$
* **Ý nghĩa:** Đo lường độ bẻ cong hình học của tuyến đường. Khoảng cách Euclid nối trực tiếp từ $A \rightarrow B$ luôn là ngắn nhất (bất đẳng thức tam giác). Việc chèn $C$ vào giữa bắt buộc xe phải đi chệch hướng.
* **Mục tiêu tối ưu:** Tối thiểu hóa thành phần này giúp ép điểm $C$ phải nằm gần trục đường thẳng nối từ $A$ đến $B$. Điều này ngăn chặn hành vi đi vòng, ép xe chạy theo các cụm không gian đồng nhất và tận dụng tối đa lộ trình có sẵn.

#### 2. $\Delta WaitTime$ (Thời gian chết phát sinh)
$$\Delta WaitTime = WaitTime_{tại\ C}$$
* **Ý nghĩa:** Khoảng thời gian xe di chuyển đến $C$ nhưng cửa sổ thời gian của $C$ chưa mở, buộc tài xế phải đứng chờ.
* **Mục tiêu tối ưu:** Thời gian chờ là thời gian chết không sinh lời. Việc phạt thời gian chờ giúp thuật toán ưu tiên chèn khách hàng vào những vị trí mà thời điểm xe lăn bánh đến nơi vừa vặn khớp với lúc khách hàng mở cửa, tối ưu hóa năng suất ca làm việc.

#### 3. $\Delta Delay$ (Hiệu ứng lan truyền dòng thời gian)
$$\Delta Delay = Departure_{mới\ tại\ B} - Departure_{cũ\ tại\ B}$$
* **Ý nghĩa:** Việc ghé qua $C$ tiêu tốn thời gian di chuyển và thời gian làm dịch vụ ($ServiceTime_C$). Điều này đẩy lùi thời điểm xe có mặt tại các điểm đứng sau $B$.
* **Mục tiêu tối ưu:** Thành phần này đóng vai trò bảo vệ "tài nguyên thời gian" cho phần còn lại của tuyến đường. Một phép chèn có thể làm tăng quãng đường rất ít, nhưng nếu nó làm chậm toàn bộ tiến độ của 20 khách hàng phía sau, đẩy họ sát vào ranh giới vi phạm cửa sổ thời gian, phép chèn đó sẽ bị phạt nặng.

---

## 4. Giai đoạn 3: Tối ưu hóa Tuyến đường bằng Local Search

Thuật toán Cheapest Insertion ở Giai đoạn 2 vốn mang bản chất **Tham lam (Greedy)**. Nó đưa ra quyết định tốt nhất tại thời điểm chèn một điểm đơn lẻ, nhưng hoàn toàn bất lực trong việc nhìn nhận bức tranh tổng thể khi tuyến đường đã đông đúc lên (đạt quy mô 50-70 điểm dừng). Hệ thống dễ dàng để lại các "vết sẹo hình học". Giai đoạn Local Search đóng vai trò là bộ lọc hậu xử lý nhằm sửa chữa các sai lầm lịch sử này.

### 4.1. Toán tử `two_opt` (Gỡ rối cấu trúc không gian)
* **Cơ chế:** Chọn ngẫu nhiên hoặc duyệt tuần tự hai cạnh bất kỳ trên lộ trình, cắt đứt chúng và đảo ngược thứ tự hành trình của đoạn nằm giữa hai cạnh đó.
* **Vai trò:** Đây là khắc tinh của hiện tượng "giao cắt hình chữ X". Trong không gian hình học phẳng, tổng độ dài hai cạnh chéo luôn lớn hơn tổng độ dài hai cạnh song song tương ứng. `two_opt` đảo ngược chuỗi điểm để biến cấu trúc chữ X lỗi thành hai đường thẳng song song mượt mà, gỡ rối không gian một cách ngoạn mục.

### 4.2. Toán tử `or_opt` (Di dời thực thể cục bộ)
* **Cơ chế:** Nhấc hẳn một điểm dừng đơn lẻ (hoặc một chuỗi ngắn gồm 2-3 điểm liên tiếp) ra khỏi vị trí hiện tại, thử nghiệm chèn nó vào tất cả các vị trí tiềm năng khác trên toàn bộ tuyến đường của ngày hôm đó.
* **Vai trò:** Sửa lỗi cho tính tham lam của bước chèn. Một điểm dừng $X$ ở đầu ngày được nhét vào vị trí vị trí số 2 vì lúc đó tuyến đường mới có 3 điểm. Khi cuối ngày tuyến đường nở rộng ra 50 điểm, việc di dời $X$ về vị trí số 45 (gần các điểm mới chèn) mới là tối ưu nhất. `two_opt` không thể làm được việc này vì nó chỉ đảo chuỗi chứ không thể dịch chuyển một phần tử đi xa.

### 4.3. Bộ điều phối `improve_route`
Hàm này đóng vai trò tổng tư lệnh, vận hành một vòng lặp chạy xen kẽ liên tục: `two_opt` $\rightarrow$ `or_opt` $\rightarrow$ `two_opt`. Vòng lặp chỉ dừng lại khi cả hai toán tử đều lắc đầu chịu trói (không thể tìm thêm bất kỳ cải thiện nào - đạt trạng thái Cực tiểu cục bộ `Local Optima`), hoặc khi chạm ngưỡng giới hạn an toàn `max_rounds` để đảm bảo tốc độ thực thi của hệ thống.

---

## 5. Đánh giá Chất lượng Lộ trình: Sự dịch chuyển từ Thời gian sang Không gian

Một trong những cải tiến quan trọng nhất trong tư duy thiết kế ở phiên bản này nằm ở **Tiêu chí nghiệm thu (Acceptance Criteria)** của giai đoạn cải thiện tuyến đường.

### 5.1. Sai lầm khi dùng `return_time` làm bộ lọc Local Search
Nếu tiếp tục dùng chỉ số thời gian xe về kho (`return_time`) để quyết định xem một bước đi Local Search (2-opt hoặc Or-opt) có thành công hay không, bộ lọc sẽ gần như bị **tê liệt**. 

Khi toán tử 2-opt gỡ thành công một nút thắt chéo, tổng quãng đường chạy xe thực tế giảm đi rõ rệt, đồng nghĩa xe sẽ di chuyển đến điểm tiếp theo sớm hơn. Tuy nhiên, do cửa sổ thời gian của khách hàng tiếp theo cố định, xe đến sớm chỉ dẫn đến việc **thời gian đứng chờ (`WaitTime`) tăng lên tương ứng**. Khi dòng thời gian lan truyền về cuối ngày, xe vẫn quay trở về kho trung tâm vào đúng giờ cũ. 

Nếu dùng thước đo `return_time`, hệ thống sẽ kết luận: *"Cải thiện bằng 0"* và đào thải phép biến đổi tốt đó.

### 5.2. Sự vượt trội của chỉ số Tổng quãng đường (`total_distance`)
Hệ thống đã nâng cấp tiêu chí đánh giá bên trong Local Search sang sử dụng **Tổng quãng đường Euclid tích lũy (`total_distance_km`)**, đồng nhất hoàn toàn với chỉ số KPI ưu tiên số 2 trong bộ công cụ `metrics.py`. 

Việc chuyển dịch này mang lại các lợi ích chiến lược:
1. **Phản ánh chính xác bản chất hình học:** Quãng đường giảm đồng nghĩa với việc gỡ rối thành công, xe đi thẳng hơn, tiết kiệm nhiên liệu, giảm hao mòn phương tiện và chi phí vận hành thực tế của doanh nghiệp.
2. **Giải phóng "Thời gian chùng dự trữ" (Slack Capacity):** Mặc dù giờ về kho chưa thay đổi ngay do bị cản bởi thời gian chờ, việc rút ngắn thời gian di chuyển thực tế trên đường đã tạo ra một lượng lớn thời gian dự trữ tại các điểm dừng. Nếu hệ thống cần chèn thêm các đơn hàng phát sinh sau này, lượng thời gian dự trữ này chính là lá chắn bảo vệ tuyến đường khỏi bị vỡ trận.

---

## 6. Tổng kết Tư duy Tối ưu Toàn diện

Sức mạnh của thuật toán CHI-LS không đến từ một hàm toán học phức tạp đơn lẻ, mà đến từ **tính đồng bộ và tính kế thừa** của một pipeline khép kín:

* **Tầm nhìn Chiến lược (Giai đoạn 1):** Lọc và ép chạy đơn rớt vĩnh viễn (`Urgent`) trước đơn linh hoạt (`Normal`) để bảo vệ tối đa **Completion Rate**.
* **Xây dựng Chiến thuật Hình học (Giai đoạn 2):** Sử dụng cơ chế chèn điểm thông minh với hàm phạt 3 thành phần (`Local Cost`) để tạo ra một bộ khung lộ trình ban đầu chặt chẽ, chống đi vòng và tiết kiệm tài nguyên thời gian downstream.
* **Tinh chỉnh và Đánh bóng Thợ thủ công (Giai đoạn 3):** Sử dụng sức mạnh cơ bắp của máy tính thông qua các toán tử `2-opt` và `Or-opt`, lấy thước đo `total_distance` làm kim chỉ nam để rà soát toàn cục, bẻ thẳng các đoạn cong lồi và tối ưu hóa chi phí vận hành ở mức triệt để nhất.

Đây là một kiến trúc cân bằng, phản ánh chính xác tư duy kỹ thuật hệ thống (Systems Engineering) trong việc giải quyết bài toán Logistics cam go trong thực tế doanh nghiệp.