import sys
from pathlib import Path
import time
from typing import Tuple

# Các import từ source code hiện tại
from main_algorithm.data_model import load_data
from main_algorithm.scheduler import weekly_scheduler_with_local_search
from test_algorithm.metrics import compute_metrics, print_metrics
from gen_output.exporter import export_weekly_result_to_csv, export_delayed_customers_to_csv, export_unfulfilled_customers_to_csv
from gen_output.weekly_route import plot_weekly_routes_interactive

DATASET_TEST = [
    ["Data/locations_new.csv", "Data/time_window_new.csv"],
    ["Data/locations.csv", "Data/time_windows.csv"]
]


def get_user_choice(menu_text: str, valid_choices: list[str]) -> str:
    """Hiển thị menu và yêu cầu người dùng nhập lựa chọn hợp lệ."""
    while True:
        print(menu_text)
        choice = input("Vui lòng chọn (1/2/3): ").strip()
        if choice in valid_choices:
            return choice
        print(f"\n[!] Lựa chọn không hợp lệ. Vui lòng nhập một trong: {', '.join(valid_choices)}\n")


def select_dataset() -> Tuple[str, str]:
    """Hiển thị menu chọn dataset và xác thực đường dẫn file."""
    menu = """
========== DATASET ==========
1. Dataset mới
2. Dataset cũ
3. Dataset khác
=============================
"""
    choice = get_user_choice(menu, ["1", "2", "3"])

    if choice == "1":
        return DATASET_TEST[0][0], DATASET_TEST[0][1]
    elif choice == "2":
        return DATASET_TEST[1][0], DATASET_TEST[1][1]
    else:
        while True:
            print("\n--- Nhập đường dẫn Dataset ---")
            loc_input = input("Đường dẫn locations.csv: ").strip()
            tw_input = input("Đường dẫn time_window.csv: ").strip()
            
            loc_path = Path(loc_input)
            tw_path = Path(tw_input)

            if not loc_path.exists():
                print(f"[!] Lỗi: Không tìm thấy file {loc_path}. Vui lòng nhập lại.")
                continue
            if not tw_path.exists():
                print(f"[!] Lỗi: Không tìm thấy file {tw_path}. Vui lòng nhập lại.")
                continue
            
            return loc_path, tw_path


def select_csv_output() -> Tuple[str, str, str]:
    """Hiển thị menu chọn nơi lưu file Output CSV."""
    menu = """
========== OUTPUT CSV ==========
1. output_new.csv - delayed_customers_new.csv - unfulfilled_customers_new.csv
2. output_old.csv - delayed_customers_old.csv - unfulfilled_customers_old.csv
3. Tự nhập
================================
"""
    choice = get_user_choice(menu, ["1", "2", "3"])
    if choice == "1":
        out_path = "Output/output_new.csv"
        delayed_customers = "Output/delayed_customers_new.csv"
        unfulfilled_customers = "Output/unfulfilled_customers_new.csv"
    elif choice == "2":
        out_path = "Output/output_old.csv"
        delayed_customers = "Output/delayed_customers_old.csv"
        unfulfilled_customers = "Output/unfulfilled_customers_old.csv"
    else:
        out_path = input("Nhập đường dẫn file output CSV (VD: Output/my_output.csv): ").strip()
        delayed_customers = input("Nhập đường dẫn file delayed_customers CSV (VD: Output/my_delayed_customers.csv): ").strip()
        unfulfilled_customers = input("Nhập đường dẫn file unfulfilled_customers CSV (VD: Output/my_unfulfilled_customers.csv): ").strip()

    return out_path, delayed_customers, unfulfilled_customers


def select_html_output() -> Path:
    """Hiển thị menu chọn nơi lưu file Output HTML."""
    menu = """
========== HTML ==========
1. weekly_routes_new.html
2. weekly_routes_old.html
3. Tự nhập
==========================
"""
    choice = get_user_choice(menu, ["1", "2", "3"])

    if choice == "1":
        out_path = "Output/weekly_routes_new.html"
    elif choice == "2":
        out_path = "Output/weekly_routes_old.html"
    else:
        out_path = input("Nhập đường dẫn file HTML (VD: Result/my_routes.html): ").strip()

    return out_path


def main():
    print("\n==================================")
    print("    Weekly Delivery Scheduler")
    print("==================================\n")

    # 1. Thu thập đường dẫn từ người dùng
    loc_path, tw_path = select_dataset()
    output_path, delayed_customers, unfulfilled_customers = select_csv_output()
    html_path = select_html_output()

    print("\n==================================")
    
    # 2. Bước 1: Load data
    print("Loading dataset...")
    try:
        depot, customer_dict = load_data(loc_path, tw_path)
    except Exception as e:
        print(f"[!] Lỗi khi load dữ liệu: {e}")
        sys.exit(1)

    # 3. Bước 2 & Bước 3 & Bước 4: Chạy thuật toán và đo thời gian
    print("Running scheduler...")
    try:
        start_time = time.perf_counter()
        result = weekly_scheduler_with_local_search(depot=depot, customers=customer_dict)
        end_time = time.perf_counter()
        runtime = end_time - start_time
        print(f"Runtime: {runtime:.3f} seconds")
    except Exception as e:
        print(f"[!] Lỗi trong quá trình chạy thuật toán: {e}")
        sys.exit(1)

    # 4. Bước 5: Sinh HTML
    print("Generating HTML...")
    try:
        delayed_by_day, _, expected_day_list = plot_weekly_routes_interactive(depot=depot, customers=customer_dict, result=result, output_filename=html_path)
        print("HTML visualization generated.")
    except Exception as e:
        print(f"[!] Lỗi khi sinh HTML: {e}")
        sys.exit(1)

    # 5. Bước 6: Xuất CSV
    print("Exporting CSV...")
    try:
        export_weekly_result_to_csv(depot=depot, customers=customer_dict, result=result, output_filename=output_path)
        delayed_df = export_delayed_customers_to_csv(customers=customer_dict, delayed_by_day=delayed_by_day, expected_day_list=expected_day_list, output_filename=delayed_customers)
        export_unfulfilled_customers_to_csv(delayed_df=delayed_df, output_filename=unfulfilled_customers)
        print("CSV exported successfully.")
    except Exception as e:
        print(f"[!] Lỗi khi xuất CSV: {e}")
        sys.exit(1)

    # 6. Bước 7: In kết quả
    result_metric = compute_metrics(depot=depot, customers=customer_dict, result=result)
    print_metrics(customers=customer_dict, m=result_metric, result=result)
    print("Done.")
    print("==================================")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] Chương trình bị gián đoạn bởi người dùng.")
        sys.exit(0)