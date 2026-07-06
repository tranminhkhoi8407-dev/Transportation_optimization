# Tài liệu Phân tích Hệ thống - Phần 5: Đánh giá Toàn diện Độ phức tạp Thuật toán (Complexity Analysis)

Tài liệu này cung cấp một đánh giá toán học nghiêm túc về mặt hiệu năng tính toán (Computational Performance) cho cả 4 phương pháp lập lịch đang được cài đặt trong hệ thống. Việc hiểu rõ độ phức tạp thời gian và không gian giúp đội ngũ dự đoán được hành vi của hệ thống khi quy mô tập dữ liệu khách hàng mở rộng (Scale-up) trong các vòng thi tiếp theo.

---

## 1. Bảng Tổng hợp Độ phức tạp Thuật toán

Gọi $N$ là tổng số khách hàng trong danh sách dữ liệu đầu vào cần xử lý ($N = 289$ trong bộ dữ liệu hiện tại). Gọi $K$ là số lượng điểm dừng tối đa có thể sắp xếp thành công trong một ngày hoạt động của một xe ($K \le N$, và trong thực tế $K \ll N$ do giới hạn cứng của ca làm việc 24 giờ).

| Phương pháp | Độ phức tạp Thời gian (Lý thuyết) | Độ phức tạp Thời gian (Thực tế hệ thống) | Độ phức tạp Không gian | Cơ chế hình thành tuyến đường |
| :--- | :--- | :--- | :--- | :--- |
| **Thuật toán Chính**<br>*(Cheapest Insertion + EDF)* | $O(N^4)$ | $O(7 \cdot K^2 \cdot N^2) pprox O(N^2)$ | $O(N)$ | Chèn tối ưu chi phí vào bất kỳ vị trí nào trên tuyến, lan truyền độ trễ |
| **Baseline 1**<br>*(Nearest Neighbor - NN)* | $O(N^2)$ | $O(7 \cdot K \cdot N) pprox O(N)$ | $O(N)$ | Nối đuôi vào cuối tuyến dựa trên khoảng cách địa lý ngắn nhất |
| **Baseline 2**<br>*(Earliest Deadline Append)* | $O(N \log N)$ | $O(N \log N)$ | $O(N)$ | Sắp xếp cố định theo hạn đóng cửa trong ngày, nối đuôi một lượt duy nhất |
| **Baseline 3**<br>*(Minimize Deferral)* | $O(N^3)$ | $O(7 \cdot K \cdot N) pprox O(N)$ | $O(N)$ | Sắp xếp cố định theo nhu cầu khối lượng, chèn vị trí theo chiến lược First-Fit |

---

## 2. Phân tích Chi tiết Từng Phương pháp

### 2.1. Thuật toán Chính (Cheapest Insertion + EDF liên ngày)

#### 1. Độ phức tạp Thời gian:
* **Vòng lặp ngoài cùng (Thời gian cuốn):** Chạy cố định qua 7 ngày trong tuần $ightarrow$ Đóng vai trò hệ số hằng số bằng 7.
* **Vòng lặp xây dựng tuyến đường ngày (`while remaining`):** Trong kịch bản tồi tệ nhất về mặt toán học (khi không có ràng buộc thời gian ca làm việc và xe có thể giao hết tất cả mọi người trong một ngày), vòng lặp này thực hiện chèn thành công từng khách hàng một, chạy tối đa $N$ lần.
* **Không gian tìm kiếm vị trí chèn tối ưu:** Bên trong vòng lặp `while`, thuật toán thực hiện một vòng lặp lồng đôi: duyệt qua mọi khách hàng còn lại trong tập ứng viên (tối đa $N$ phần tử) và duyệt qua mọi vị trí chỉ mục chèn khả dĩ trên tuyến đường hiện tại (tối đa $N$ vị trí). Phép toán lồng nhau này tốn $O(N^2)$ chi phí tính toán.
* **Hàm kiểm tra lan truyền thời gian (`try_insert_at_position`):** Tại mỗi cấu hình vị trí thử nghiệm cụ thể, thuật toán thực hiện một vòng lặp dọc theo tuyến đường để đẩy lùi dòng thời gian của toàn bộ các điểm dừng cũ nằm phía sau vị trí chèn. Trong kịch bản tệ nhất, vòng lặp lan truyền này duyệt qua $O(N)$ điểm dừng.
* **Tổng hợp lý thuyết Chặn trên nghiêm ngặt (Strict Upper Bound):** $$T_{	ext{main\_theory}} = 7 	imes O(N) 	imes [O(N) 	imes O(N) 	imes O(N)] = O(N^4)$$
* **Đánh giá Thực tế Hệ thống:** Trong thực tế vận hành logistics, số lượng điểm dừng tối đa $K$ mà một xe có thể ghé thăm trong vòng 24 giờ bị giới hạn rất chặt bởi ràng buộc thời gian phục vụ (`service_time`) và thời gian di chuyển. Do đó, mảng danh sách `stops` của một ngày không bao giờ vượt quá hằng số $K$ ($K \ll N$). Vòng lặp tìm chỉ mục vị trí chèn thực tế chỉ chạy $K$ lần, và vòng lặp lan truyền dòng thời gian phía sau cũng chỉ duyệt tối đa $K$ phần tử. 
    Vì vậy, chi phí thời gian thực tế của hệ thống hoạt động ở mức hiệu năng:
    $$T_{	ext{main\_real}} = 7 	imes K 	imes [N 	imes K 	imes O(K)] = O(7 \cdot K^3 \cdot N) pprox O(N)$$
    Xét trên khía cạnh thực nghiệm mở rộng không tính giới hạn thời gian ca làm việc, thuật toán chạy ổn định ở tốc độ $O(N^3)$. Phép toán chiếm tài nguyên CPU lớn nhất (đóng vai trò thống trị thời gian chạy) chính là vòng lặp lồng đôi quét tìm cặp khách hàng và vị trí chèn tối ưu trong hàm `day_route_cheapest_insertion`.

#### 2. Độ phức tạp Không gian:
* Hệ thống duy trì từ điển `pending` lưu trữ trạng thái của $N$ khách hàng. Cấu trúc kết quả `WeeklyResult` lưu trữ rải rác các điểm dừng trên 7 ngày với tổng số điểm dừng toàn tuần không vượt quá $N$. Các mảng sao chép lộ trình tạm thời trong quá trình thử chèn chiếm không gian bộ nhớ tuyến tính $O(N)$. Tổng độ phức tạp không gian đạt mức tối ưu: $O(N)$.

---

### 2.2. Baseline 1 (Nearest Neighbor)

#### 1. Độ phức tạp Thời gian: $O(N^2)$
* **Giải trình:** * Vòng lặp `while remaining` chạy tối đa $N$ lần để tìm kiếm và thêm từng khách hàng vào lộ trình.
    * Bên trong vòng lặp, thuật toán duyệt qua danh sách các đối tượng còn lại trong tập ứng viên (tối đa $N$ phần tử) để tính khoảng cách hình học phẳng.
    * Hàm kiểm tra hợp lệ nối đuôi `_try_append_at_end` hoạt động trong thời gian hằng số $O(1)$ vì nó chỉ kiểm tra duy nhất một phép toán tính dòng thời gian từ điểm dừng cuối cùng hiện tại tới khách hàng mới và đường chạy về kho, hoàn toàn không có cơ chế lan truyền thời gian phức tạp.
    * Do đó, tổng chi phí thời gian lý thuyết là: $N 	imes O(N) = O(N^2)$. Khi áp dụng hằng số ca làm việc $K$, chi phí thực tế giảm xuống chỉ còn $O(7 \cdot K \cdot N) pprox O(N)$. Thuật toán này chạy cực kỳ nhanh nhưng chất lượng tuyến đường sẽ kém hơn do tính tham lam cục bộ cao.

#### 2. Độ phức tạp Không gian: $O(N)$
* Chỉ lưu trữ danh sách ứng viên và mảng điểm dừng tuần tự trong bộ nhớ RAM, đạt mức tuyến tính $O(N)$.

---

### 2.3. Baseline 2 (Earliest Deadline Append)

#### 1. Độ phức tạp Thời gian: $O(N \log N)$
* **Giải trình:** * Thuật toán sử dụng hàm sắp xếp tiêu chuẩn của Python `sorted(candidates, key=day_deadline)` dựa trên thuật toán Timsort. Chi phí thời gian cho phép sắp xếp này là $O(N \log N)$.
    * Sau khi sắp xếp cố định, thuật toán chạy duy nhất một vòng lặp tuyến tính `for cust in ordered:` quét qua danh sách đúng 1 lần (tối đa $N$ bước).
    * Tại mỗi bước, gọi hàm nối đuôi `_try_append_at_end` với chi phí hằng số $O(1)$. Vòng lặp này tốn chi phí thời gian $O(N)$.
    * Do đó, phép toán sắp xếp Timsort đóng vai trò thống trị hoàn toàn thời gian chạy của thuật toán. Tổng độ phức tạp thời gian đạt mức rất thấp: $O(N \log N)$.

#### 2. Độ phức tạp Không gian: $O(N)$
* Mảng sắp xếp `ordered` và cấu trúc lưu trữ điểm dừng ngày chiếm không gian bộ nhớ tuyến tính $O(N)$.

---

### 2.4. Baseline 3 (Minimize Deferral / Maximum Packing)

#### 1. Độ phức tạp Thời gian: $O(N^3)$
* **Giải trình:**
    * Giai đoạn đầu thực hiện sắp xếp danh sách ứng viên theo nhu cầu khối lượng hàng hóa tăng dần, tốn chi phí $O(N \log N)$.
    * Vòng lặp chính duyệt qua danh sách đã sắp xếp `for cust in ordered:` chạy tối đa $N$ lần.
    * Bên trong vòng lặp, ứng với mỗi khách hàng, thuật toán chạy một vòng lặp thử vị trí chèn `pos` từ đầu tuyến đến cuối tuyến hiện tại (tối đa $N$ vị trí chỉ mục).
    * Tại mỗi chỉ mục, gọi hàm thuật toán chính `try_insert_at_position` để tính toán lan truyền thời gian cho các điểm dừng phía sau (tối đa $N$ điểm dừng). Phép toán lồng nhau này tốn $O(N 	imes N) = O(N^2)$ chi phí tính toán.
    * Tuy nhiên, do áp dụng chiến lược **First-Fit**, vòng lặp tìm vị trí chèn sẽ ngắt (`break`) ngay lập tức khi tìm thấy phương án hợp lệ đầu tiên, giúp giảm thiểu đáng kể chi phí chạy thực tế trên máy tính.
    * Tổng hợp lý thuyết Chặn trên nghiêm ngặt đạt mức: $O(N \log N) + [N 	imes O(N^2)] = O(N^3)$. Khi áp dụng giới hạn ca làm việc thực tế $K$, chi phí vận hành thực tế rút gọn về mức hiệu năng tuyến tính $O(7 \cdot K \cdot N) pprox O(N)$.

#### 2. Độ phức tạp Không gian: $O(N)$
* Lưu trữ danh sách đã sắp xếp và các mảng stop cập nhật dòng thời gian tạm thời trong bộ nhớ RAM, đạt mức tuyến tính $O(N)$.
