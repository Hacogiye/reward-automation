"use strict";
// Chuyển giao diện Tiếng Việt <-> English. Giao diện viết bằng tiếng Việt; ở chế độ English, bộ dịch đi qua các nút chữ
// (và title / placeholder / aria-label) rồi thay bằng bản tiếng Anh trong từ điển bên dưới. MutationObserver dịch luôn
// mọi thứ app vẽ ra sau đó (biểu đồ, thông báo...), nên code giao diện không phải gọi hàm dịch ở từng chỗ.
// Khóa từ điển: chữ tiếng Việt đã gộp khoảng trắng; mọi con số được thay bằng "#" (vd "còn # điểm") rồi điền lại theo thứ tự.
// Không dịch: dòng nhật ký do bot ghi (.msg), tên tài khoản trong nhật ký, code, và các khối có data-lang (bản EN viết sẵn).

const I18N = (() => {
  const EN = {
    // ---- khung, menu, chung
    "Điểm mỗi ngày trong # ngày gần nhất, tổng # điểm": "Points per day over the last # days, # points in total",
    "Số điểm trong # ngày: từ # đến #": "Points over # days: from # to #",
    "Nguồn điểm # ngày, tổng # điểm": "Points by source over # days, # in total",
    "So sánh điểm mỗi ngày của # tài khoản trong # ngày": "Daily points of # accounts over # days",
    // ---- màn hình chào, đồng ý rủi ro, đăng nhập
    "Chào mừng": "Welcome", "Bước #": "Step #", "Tiếp tục": "Continue", "Quay lại": "Back",
    "Bot tự làm các việc Microsoft Rewards hằng ngày cho nhiều tài khoản: search PC và Mobile, Daily Set, Quests, Visual Search. Thiết lập mất khoảng # phút.":
      "The bot does your daily Microsoft Rewards tasks for several accounts: PC and Mobile searches, Daily Set, Quests, Visual Search. Setup takes about # minutes.",
    "Tôi đã hiểu và tự chịu rủi ro khi dùng app": "I understand and accept the risk of using this app",
    "Thêm tài khoản Microsoft đầu tiên. Sau đó bấm": "Add your first Microsoft account. Then click",
    "một lần cho tài khoản đó, rồi": "once for that account, then",
    "Có thể làm sau ở trang": "You can do this later on the", ". Mở lại màn hình này ở": "page. Reopen this screen from",
    "Xem lại màn hình chào": "Show the welcome screen again",
    "Trong cửa sổ trình duyệt vừa mở, đăng nhập ở tab": "In the browser window that just opened, sign in on the",
    "Xem tab": "Check the", ": góc phải phải là": "tab: the top right must show the",
    "cùng tài khoản": "same account", "Đóng cửa sổ trình duyệt, rồi bấm": "Close the browser window, then click",
    "bên dưới.": "below.", "Để sau": "Later",
    "Thu gọn thanh bên": "Collapse sidebar", "Mở rộng thanh bên": "Expand sidebar", "Thu gọn": "Collapse",
    // ---- văn phòng
    "Văn phòng": "Office", "Văn phòng bot": "Bot office", "Bật nhạc lofi": "Play lofi", "Tắt nhạc lofi": "Stop lofi",
    "Tiếng mưa": "Rain sounds", "Âm lượng": "Volume", "Nhạc đang tắt": "Music is off", "Lofi tự sinh": "Generated lofi",
    "mưa": "rain", "# robot đang làm việc": "# robots working", "# đang nghỉ": "# on break", "đang làm": "working", "# đang làm": "# working",
    "Xong việc rồi!": "All done!", "Xem tổng quan của tài khoản này": "Open this account's overview",
    "Xem nhanh tài khoản này": "Quick look at this account", "Thông tin tài khoản": "Account info",
    "Chưa lưu email đăng nhập": "No sign-in email saved", "Đã làm": "Done",
    "Đã làm hết việc hôm nay": "Everything done for today", "Chưa làm việc nào": "Nothing done yet", "+# việc khác": "+# more",
    "Chưa có dữ liệu task. Bấm": "No task data yet. Click",
    "Chưa có tài khoản nào. Bấm dấu + để thêm nhân viên đầu tiên.": "No accounts yet. Click + to hire your first robot.",
    "Nhật ký: hôm nay # điểm": "Diary: # points today",
    "Chuỗi # ngày liên tiếp": "# days in a row", "Đã xong # việc hôm nay": "# tasks done today",
    "Còn # điểm nữa là tới mục tiêu": "# points left to the goal", "Đủ điểm đổi quà rồi!": "Enough points for the reward!",
    "Hôm nay chưa có gì để ghi": "Nothing to write about today yet",
    "Văn phòng: mỗi robot là một tài khoản đang được bot chạy": "Office: each robot is one account the bot runs",
    "Tổng quan": "Overview", "Tài khoản": "Accounts", "Nhật ký": "Log", "Lịch sử": "History", "Cài đặt": "Settings",
    "Hướng dẫn": "Guide", "# tài khoản": "# accounts", "Đang nghỉ": "Idle", "Sáng": "Light", "Tối": "Dark",
    "Theo hệ thống": "System", "Giao diện": "Appearance", "Ngôn ngữ": "Language", "Lưu": "Save", "Hủy": "Cancel",
    "Đóng": "Close", "Sửa": "Edit", "Xóa": "Delete", "Chạy": "Run", "Dừng": "Stop", "Kiểm tra": "Check",
    "Đăng nhập": "Log in", "Làm mới": "Refresh", "Sao chép": "Copy", "Tất cả": "All", "Lỗi": "Error",
    "Cảnh báo": "Warning", "Xong": "Done", "điểm": "points", "# điểm": "# points", "# ngày": "# days", "# tuần": "# weeks",
    "# ngày gần nhất": "last # days", "lượt": "times", "bước": "steps", "Ít": "Less", "Nhiều": "More",
    "T2": "Mon", "T3": "Tue", "T4": "Wed", "T5": "Thu", "T6": "Fri", "T7": "Sat", "CN": "Sun",
    // ---- trạng thái (từ bot)
    "Sẵn sàng": "Ready", "Đang chạy": "Running", "Đang chờ": "Waiting", "Đang làm mới": "Refreshing",
    "Đang đăng nhập": "Logging in", "Đang kiểm tra": "Checking", "Hoàn thành": "Done", "Chưa đăng nhập": "Not logged in",
    "Đã dừng": "Stopped", "Chờ lượt chạy": "Waiting for a slot", "Khởi động": "Starting", "Bấm Đăng nhập": "Click Log in",
    "Đóng cửa sổ khi xong": "Close the window when done", "Tự đăng nhập lại": "Auto re-login",
    "Kiểm tra: tất cả OK": "Check: all OK", "Kiểm tra: có cảnh báo": "Check: warnings", "Kiểm tra: có lỗi": "Check: errors",
    "Profile đang mở ở cửa sổ khác": "Profile is open in another window",
    "bing.com đăng nhập sai tài khoản": "bing.com is logged in to the wrong account",
    // ---- tổng quan
    "Chạy tài khoản này": "Run this account", "Chỉ đọc điểm, không làm task": "Only reads points, does no tasks",
    "Thêm tài khoản đầu tiên": "Add your first account", "Chưa có tài khoản": "No accounts yet",
    "Hôm nay": "Today", "Tháng này": "This month", "Trọn đời": "Lifetime", "Thẻ đóng dấu hôm nay": "Today's stamp card",
    "# dấu": "# stamps", "Chưa có dữ liệu. Bấm": "No data yet. Click", "để đọc task hôm nay từ Rewards.": "to read today's tasks from Rewards.",
    "Chưa làm": "Not done", "Đã xong": "Done", "chưa có dữ liệu": "no data yet", "Daily streak liên tiếp": "Daily streak in a row",
    "Còn": "Need", "dấu nữa để nhận": "more stamps to get",
    "điểm. Giữ các chuỗi streak bên cạnh mỗi ngày để nhận dấu.": "points. Keep the streaks on the right going every day to earn stamps.",
    "Chưa đọc được số dấu.": "Could not read the stamp count.", "Đã đủ # dấu: vào Rewards để nhận": "All # stamps collected: go to Rewards to claim",
    "điểm.": "points.", "# trên # dấu": "# of # stamps", "Hôm nay xong": "Done today", "Hôm nay chưa": "Not yet today",
    "Ngày #": "Day #", "ngày tới # điểm": "next day # points",
    "Task hôm nay": "Today's tasks", "Ẩn việc đã xong": "Hide finished tasks", "Xong hết": "All done",
    "Chưa có dữ liệu task cho tài khoản này.": "No task data for this account yet.", "Tìm kiếm": "Search",
    "Hoạt động": "Activity", "Task thêm": "Extra tasks", "Cập nhật # #": "Updated # #",
    "Đặt mục tiêu đổi quà": "Set a reward goal", "Sửa mục tiêu": "Edit goal", "còn": "",
    "điểm · khoảng": "points left · about", "(#), trung bình #ngày": "(#), averaging #day",
    "điểm · chưa đủ lịch sử để dự đoán": "points left · not enough history to predict",
    "Đủ điểm rồi, vào trang Redeem để đổi": "Enough points, go to the Redeem page to redeem",
    // ô số liệu + biểu đồ
    "Trung bình # ngày": "#-day average", "điểm/ngày, tính trên # ngày có số liệu": "points/day, over # days with data",
    "chưa có lịch sử": "no history yet", "Chuỗi đủ điểm search": "Full search streak",
    "hôm nay đã đủ PC + Mobile": "PC + Mobile full today", "hôm nay chưa đủ PC + Mobile": "PC + Mobile not full today",
    "#% so với cùng kỳ tháng trước": "#% vs the same days last month", "chưa có số liệu tháng trước để so": "no data from last month to compare",
    "chưa đọc được điểm search": "search points not read yet",
    "Điểm mỗi ngày": "Points per day", "Số điểm hiện có": "Available points", "Điểm": "Points",
    "Độ đều đặn": "Consistency", "Điểm đến từ đâu": "Where points come from", "So sánh tài khoản": "Compare accounts",
    "điểm mỗi ngày": "points per day", "# ngày có điểm": "# days with points", "# # điểm": "# # points",
    "# không có số liệu": "# no data", "# trên # ngày có điểm trong # tuần": "# of # days with points in # weeks",
    "Chưa có lịch sử. Mỗi lần chạy hoặc làm mới sẽ ghi lại điểm của ngày đó.": "No history yet. Every run or refresh records that day's points.",
    "Chưa có lịch sử điểm.": "No points history yet.", "Chưa có số liệu điểm search / thẻ.": "No search / card points yet.",
    // ---- tài khoản
    "Thêm tài khoản": "Add account", "Dừng tất cả": "Stop all", "Chạy tất cả": "Run all",
    "Chạy mọi tài khoản và làm mọi việc (Daily Set, Quests, Visual Search, PC, Mobile, Browse), bỏ qua các công tắc đang tắt":
      "Run every account and do every task (Daily Set, Quests, Visual Search, PC, Mobile, Browse), ignoring switches that are off",
    "Chạy mọi tài khoản theo các công tắc bên dưới": "Run every account using the switches below",
    "Chế độ": "Mode", "Trạng thái": "Status", "Tiến độ": "Progress", "Cửa sổ riêng": "Own window", "Edge đang mở": "Open Edge",
    "cổng #": "port #", "tự đăng nhập": "auto login", "Việc bot sẽ làm khi chạy": "What the bot does on a run",
    "Bấm từng thẻ task, làm quiz và poll": "Opens each task card, answers quizzes and polls",
    "Làm từng bước của các quest nhiều bước ở trang Earn (bước cần app điện thoại / app máy tính thì bỏ qua)":
      "Works through multi-step quests on the Earn page (steps that need the phone or desktop app are skipped)",
    "Tìm bằng # ảnh qua nút camera của Bing (mỗi ngày # lượt)": "Searches with # image via Bing's camera button (# per day)",
    "Tìm đến khi đủ điểm search máy tính": "Searches until desktop search points are full",
    "Giả lập điện thoại, tìm đến khi đủ điểm": "Emulates a phone, searches until the points are full",
    "Lướt web tối đa # phút cho Edge – Minutes, đo số phút mỗi # phút": "Browses up to # minutes for Edge – Minutes, measuring every # minutes",
    "Tự dừng khi không được tính phút": "Stop when minutes aren't counted",
    "Tự chọn số lượt search": "Choose the number of searches",
    "Tắt thì search đến khi đủ điểm tối đa. Bật thì search đến đúng số lượt trong ngày ở dưới (# điểm/lượt) rồi dừng":
      "Off: search until the maximum points. On: stop once the day reaches the number of searches below (# points each)",
    "Số lượt search trong ngày": "Searches per day",
    "Số lượt search cần từ # đến #": "The number of searches must be between # and #",
    "Đã lưu số lượt search": "Number of searches saved",
    "Edge – Minutes không tăng sau # phút thì dừng. Tắt để luôn lướt đủ # phút":
      "Stop if Edge – Minutes hasn't grown after # minutes. Turn off to always browse the full # minutes",
    "Chạy ẩn": "Run hidden", "Không hiện cửa sổ trình duyệt": "Don't show the browser window",
    "Số tài khoản chạy cùng lúc": "Accounts running at once",
    // hộp thoại tài khoản / mục tiêu
    "Sửa tài khoản": "Edit account", "Tên": "Name", "Đổi ảnh": "Change photo", "Xóa ảnh": "Remove photo",
    "Cách mở trình duyệt": "How the browser opens", "Cửa sổ riêng do app mở": "Own window opened by the app",
    "Nên dùng. Mỗi tài khoản một thư mục đăng nhập riêng.": "Recommended. Each account gets its own login folder.",
    "Gắn vào Edge đang mở": "Attach to an open Edge", "Edge bạn tự mở với cổng debug.": "An Edge you open yourself with a debug port.",
    "Cổng debug": "Debug port", "Proxy riêng": "Own proxy",
    "socks5://1.2.3.4:1080 hoặc http://host:8080": "socks5://1.2.3.4:1080 or http://host:8080","(không bắt buộc)": "(optional)", "Email tài khoản Microsoft": "Microsoft account email",
    "Mật khẩu": "Password", "Đã lưu (để trống = giữ nguyên)": "Saved (leave empty to keep)", "Xóa mật khẩu đã lưu": "Delete saved password",
    "Nhập mật khẩu cho email này (hoặc xóa email để không tự đăng nhập).": "Enter the password for this email (or clear the email to turn off auto login).",
    'Muốn bỏ tự đăng nhập thì tick "Xóa mật khẩu đã lưu".': 'To turn off auto login, tick "Delete saved password".',
    "Không đọc được ảnh này. Chọn file PNG, JPEG hoặc WebP.": "Couldn't read this image. Pick a PNG, JPEG or WebP file.",
    "Mục tiêu đổi quà": "Reward goal", "Món muốn đổi": "Reward to redeem", "Vd: Thẻ quà Amazon #$": "E.g. Amazon #$ gift card",
    "Số điểm cần": "Points needed", "Vd: #": "E.g. #", "Xóa mục tiêu": "Delete goal",
    "Xem số điểm của từng món ở trang Redeem trên rewards.bing.com.": "See each reward's price on the Redeem page at rewards.bing.com.",
    "Nhập số điểm cần (số nguyên lớn hơn #).": "Enter the points needed (a whole number above #).",
    // ---- nhật ký
    "Tất cả tài khoản": "All accounts", "Xóa nhật ký": "Clear log", "Lọc theo mức": "Filter by level",
    "Chưa có nhật ký": "No log yet", "Bấm": "Click",
    "lượt chạy #": "run #", "kiểm tra #": "check #",
    // ---- lịch sử
    "Mỗi ngày làm được gì, còn thiếu gì": "What got done each day, and what was missed", "Ngày": "Date",
    "Điểm trong ngày": "Points that day", "Thẻ & hoạt động": "Cards & activities", "Còn thiếu": "Still missing",
    "Đủ hết": "All done",
    "Chưa có lịch sử. Mỗi lần chạy hoặc làm mới sẽ ghi lại số liệu của ngày đó.": "No history yet. Every run or refresh records that day's numbers.",
    "Số liệu được ghi mỗi lần bot chạy hoặc làm mới. Ngày không chạy thì không có dòng.":
      "Numbers are recorded each time the bot runs or refreshes. Days without a run have no row.",
    "Theo ngày": "By day", "Khoảng thời gian": "Period", "Ngày có số liệu": "Days with data",
    "Tổng điểm kiếm được": "Points earned", "Trung bình mỗi tài khoản/ngày": "Average per account per day",
    "Ngày đủ điểm search": "Days with full search points", "PC và Mobile": "PC and Mobile",
    "Tìm trong nhật ký": "Search the log", "Không có dòng nào khớp": "No matching lines",
    "Thử từ khóa khác hoặc chọn lại mức lọc.": "Try another keyword or change the level filter.",
    // ---- cài đặt
    "Lưu cài đặt": "Save settings", "Search & trình duyệt": "Search & browser",
    "Nghỉ ít nhất giữa # lượt search": "Shortest pause between # searches",
    "Nghỉ nhiều nhất giữa # lượt search": "Longest pause between # searches",
    "Bot chờ một khoảng ngẫu nhiên giữa mức ít nhất và nhiều nhất.": "The bot waits a random time between the shortest and longest pause.",
    "Số lượt search thêm": "Extra searches",
    "Search thêm vài lượt sau khi đủ điểm, phòng khi Rewards cập nhật chậm.": "A few more searches after the points are full, in case Rewards updates late.",
    "Dừng khi không được cộng điểm sau": "Stop when not credited after",
    "Số lượt liên tiếp không lên điểm thì dừng loại search đó và ghi lý do vào nhật ký.":
      "After this many searches in a row without points, that search type stops and the reason is logged.",
    "Không lặp lại câu search trong": "Don't repeat a search query within",
    "Câu đã dùng không được dùng lại trong khoảng này, ở mọi tài khoản.": "A used query isn't used again within this period, on any account.",
    "Hành vi giống người dùng": "User-like behaviour",
    "Lướt trang kết quả trong lúc chờ": "Browse the results while waiting",
    "Cuộn đọc trang kết quả và thỉnh thoảng mở một kết quả, trong đúng thời gian nghỉ giữa # lượt search.":
      "Scrolls the results page and sometimes opens a result, within the normal pause between # searches.",
    "Tỉ lệ lượt search có mở một kết quả": "Share of searches that open a result",
    "Bỏ qua quảng cáo và link tải file.": "Ads and file downloads are skipped.",
    "Task": "Tasks", "Thời gian Browse tối đa": "Maximum Browse time",
    "Thời gian lướt web cho Edge – Minutes trong một lượt chạy.": "Time spent browsing for Edge – Minutes in one run.",
    "Số lần thử Visual Search mỗi ngày": "Visual Search tries per day",
    "Bing chặn khi một tài khoản thử quá nhiều lần trong ngày.": "Bing blocks an account that tries too often in one day.",
    "Trình duyệt": "Browser", "Trình duyệt cho cửa sổ riêng": "Browser for own windows",
    "Trình duyệt bot mở cho mỗi tài khoản. Nên dùng Edge.": "The browser the bot opens for each account. Edge is recommended.",
    "Không đi qua proxy hệ thống": "Bypass the system proxy",
    "Chặn proxy chen giữa. Tắt nếu mạng của bạn bắt buộc đi qua proxy.": "Blocks man-in-the-middle proxies. Turn off if your network requires a proxy.",
    "Dữ liệu": "Data", "Giữ file nhật ký": "Keep log files",
    "File cũ hơn trong data/logs tự xóa khi bot chạy.": "Older files in data/logs are deleted when the bot runs.",
    "giây": "sec", "phút": "min", "lần": "tries", "ngày": "days",
    "Chạy nhiều cửa sổ cùng lúc": "Running several windows at once",
    "Phiên bản #": "Version #", "Phiên bản # (mã nguồn)": "Version # (source)",
    // ---- thẻ Giới thiệu, thư mục nhật ký
    "Giới thiệu": "About", "Thư mục dữ liệu": "Data folder", "Mở thư mục nhật ký": "Open log folder",
    "Mở thư mục": "Open folder", "Mở thư mục data/logs": "Open the data/logs folder",
    "Tự làm các việc Microsoft Rewards hằng ngày cho nhiều tài khoản.": "Does your daily Microsoft Rewards tasks for several accounts.",
    "Điều khoản của Microsoft Rewards không cho phép dùng bot. Bạn tự chịu rủi ro khi dùng app.":
      "The Microsoft Rewards terms do not allow bots. You use this app at your own risk.",
    "Thư viện và giấy phép": "Libraries and licences",
    "Bản đầy đủ của từng giấy phép nằm trong thư mục": "The full text of each licence is in the", "của app.": "folder of the app.",
    // ---- hướng dẫn (phần tiêu đề; nội dung có bản EN viết sẵn)
    "Hướng dẫn sử dụng": "User guide", "Cách dùng app từ lúc thêm tài khoản đến khi chạy tự động mỗi ngày.":
      "How to use the app, from adding an account to running it automatically every day.",
    // ---- chế độ vui, trạng thái rỗng, lỗi, xác nhận
    "Chế độ vui (Văn phòng robot, skin Cyberpunk, icon 3D)": "Fun mode (robot office, Cyberpunk skin, 3D icons)",
    "Tiến độ hôm nay": "Today's progress", "# xong": "# done", "Thêm biểu đồ": "More charts", "Thêm thao tác": "More actions",
    "# trên # ngày": "# of # days",
    "Chạy mọi task một lần": "Run every task once",
    "Chạy mọi task một lần: làm mọi việc kể cả công tắc đang tắt, chỉ lần này và không đổi cài đặt đã lưu.":
      "Run every task once: does every task, even switches that are off, for this run only and without changing saved settings.",
    "Thêm một tài khoản Microsoft, đăng nhập một lần rồi bot sẽ làm việc thay bạn.":
      "Add a Microsoft account, log in once, and the bot does the work for you.",
    "Thêm tài khoản, bấm Đăng nhập một lần rồi chạy.": "Add an account, click Log in once, then run.",
    "Chưa có lịch sử": "No history yet", "Mỗi lần chạy hoặc làm mới sẽ ghi lại số liệu của ngày đó.": "Every run or refresh records that day's numbers.",
    "Đến trang Tài khoản": "Go to Accounts",
    "Chạy hoặc kiểm tra một tài khoản, từng bước bot làm sẽ hiện ở đây.": "Run or check an account, and every step the bot takes shows up here.",
    "Xóa tài khoản?": "Delete account?",
    "Tài khoản sẽ bị xóa khỏi app. Phiên đăng nhập trong data/profiles vẫn được giữ.":
      "The account will be removed from the app. The login session in data/profiles is kept.",
    "Có lỗi xảy ra": "Something went wrong",
    // ---- thông báo (toast)
    "Bắt đầu chạy": "Started", "Bắt đầu làm tất cả các việc": "Started doing every task", "Đang làm mới điểm": "Refreshing points",
    "Đã mở cửa sổ đăng nhập": "Login window opened", "Đang kiểm tra (không search)": "Checking (no searches)",
    "Đã gửi lệnh dừng": "Stop sent", "Đã lưu cài đặt": "Settings saved", "Đã lưu tài khoản": "Account saved",
    "Đã thêm tài khoản. Bấm Đăng nhập để đăng nhập lần đầu.": "Account added. Click Log in to log in the first time.",
    "Đã lưu mục tiêu": "Goal saved", "Đã xóa mục tiêu": "Goal deleted",
    "Nhật ký hoạt động": "Activity log", "Nhật ký đang trống": "The log is empty", "Đã sao chép nhật ký": "Log copied",
    "Đã chọn toàn bộ nhật ký, bấm Ctrl+C để sao chép": "Selected the whole log, press Ctrl+C to copy",
  };
  // chuỗi có dữ liệu của người dùng (tên tài khoản, email...) ở giữa: dịch theo mẫu, phần ở giữa giữ nguyên hoặc dịch tiếp
  const PATTERNS = [
    [/^(.+) \(bấm để đổi\)$/, (m) => `${tr(m[1]) ?? m[1]} (click to change)`],
    [/^Tài khoản (.+): hiện có (.+) điểm\.$/, (m) => `Account ${m[1]}: ${m[2]} points now.`],
    [/^Đã lưu mật khẩu \(mã hóa\) cho (.+): phiên hết hạn thì bot tự đăng nhập lại$/,
      (m) => `Password saved (encrypted) for ${m[1]}: when the session expires the bot logs in again`],
    [/^“(.+)” cần là số từ (\d+) đến (\d+)$/, (m) => `“${tr(m[1]) ?? m[1]}” must be a number from ${m[2]} to ${m[3]}`],
    [/^Đang dừng (.+)$/, (m) => `Stopping ${m[1]}`],
    [/^Đăng nhập cho tài khoản (.+)$/, (m) => `Signing in account ${m[1]}`],
  ];
  const NUM = /[+\-]?\d[\d,.:/-]*/g;  // vd "3,083", "+10", "60/90", "14:16", "09-11"

  // bản dịch của 1 chuỗi, hoặc null nếu không có
  function tr(text) {
    const core = text.replace(/\s+/g, " ").trim();
    if (!core) return null;
    if (EN[core] !== undefined) return EN[core];
    const nums = core.match(NUM);
    if (nums) {
      const val = EN[core.replace(NUM, "#")];
      if (val !== undefined) { let i = 0; return val.replace(/#/g, () => nums[i++] ?? "#"); }
    }
    for (const [re, f] of PATTERNS) { const m = core.match(re); if (m) return f(m); }
    if (core.includes(" · ")) {  // "Trạng thái · tiến độ", "Tên thẻ · Chưa làm · +10 điểm"
      const parts = core.split(" · "), out = parts.map((p) => tr(p) ?? p);
      if (out.some((x, i) => x !== parts[i])) return out.join(" · ");
    }
    return null;
  }

  const SKIP = "[data-lang], #logbox .msg, #logbox .nm, code, pre, script, style, [data-no-i18n]";
  const ATTRS = ["title", "placeholder", "aria-label"];
  const origText = new WeakMap(), origAttr = new WeakMap();
  let lang = "vi", observer = null;

  function doText(node) {
    const el = node.parentElement;
    if (!el || el.closest(SKIP)) return;
    const v = node.nodeValue, t = tr(v);
    if (t === null) return;
    const lead = v.match(/^\s*/)[0], trail = v.match(/\s*$/)[0];
    const out = lead + t + trail;
    if (out === v) return;
    origText.set(node, v);
    node.nodeValue = out;
  }
  function doAttrs(el) {
    if (el.closest(SKIP)) return;
    for (const a of ATTRS) {
      const v = el.getAttribute(a);
      if (!v) continue;
      const t = tr(v);
      if (t === null || t === v) continue;
      const o = origAttr.get(el) || {};
      o[a] = v; origAttr.set(el, o);
      el.setAttribute(a, t);
    }
  }
  function walk(root) {
    if (root.nodeType === Node.TEXT_NODE) { doText(root); return; }
    if (root.nodeType !== Node.ELEMENT_NODE) return;
    doAttrs(root);
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let n;
    while ((n = w.nextNode())) n.nodeType === Node.TEXT_NODE ? doText(n) : doAttrs(n);
  }
  function restore(root) {
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let n = root;
    do {
      if (n.nodeType === Node.TEXT_NODE && origText.has(n)) { n.nodeValue = origText.get(n); origText.delete(n); }
      if (n.nodeType === Node.ELEMENT_NODE && origAttr.has(n)) {
        for (const [a, v] of Object.entries(origAttr.get(n))) n.setAttribute(a, v);
        origAttr.delete(n);
      }
    } while ((n = w.nextNode()));
  }

  function apply(next) {
    lang = next === "en" ? "en" : "vi";
    document.documentElement.lang = lang;
    if (observer) { observer.disconnect(); observer = null; }
    if (lang === "vi") { restore(document.body); return; }
    walk(document.body);
    observer = new MutationObserver((muts) => {
      for (const m of muts) {
        if (m.type === "childList") m.addedNodes.forEach(walk);
        else if (m.type === "characterData") doText(m.target);
        else if (m.type === "attributes") doAttrs(m.target);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  }

  return { apply, tr, get lang() { return lang; } };
})();
