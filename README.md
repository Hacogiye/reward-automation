# Microsoft Rewards Bot (giao diện, nhiều tài khoản)

Tự làm Daily Set, Keep earning (link, poll, quiz cơ bản), search PC + Mobile, search ảnh trên Bing Images
và browse web trong N phút. Chạy được nhiều tài khoản/cửa sổ **song song**, có dashboard theo dõi điểm và task.

> ⚠️ **Đọc trước khi dùng.** Điều khoản của Microsoft Rewards cấm dùng bot hay công cụ tự động để kiếm điểm. Microsoft
> có thể **khóa tài khoản Rewards, hủy điểm chưa đổi hoặc hủy quà đã đổi**. Dự án này chỉ để học và nghiên cứu, không
> liên quan và không được Microsoft xác nhận. Bạn tự chịu mọi rủi ro khi dùng, tác giả không chịu trách nhiệm cho việc
> tài khoản bị khóa hay mất điểm. Không nên dùng với tài khoản Microsoft chính mà bạn không muốn mất.

## Cài đặt

**Cách dễ nhất (Windows, không cần Python):** tải `RewardsBot-<phiên bản>-win64.zip` ở trang
[Releases](https://github.com/NT101-lc/reward-automation/releases), giải nén vào một thư mục cố định (vd
`C:\RewardsBot`), chạy `RewardsBot.exe`. Máy cần có Microsoft Edge (Windows 10/11 có sẵn). Dữ liệu (tài khoản, phiên
đăng nhập, cài đặt) nằm trong `data\` cạnh `RewardsBot.exe`.

**Từ mã nguồn:**
```bash
pip install -r requirements.txt
```

Mặc định app dùng Microsoft Edge có sẵn trên Windows. Nếu muốn dùng Chromium của Playwright, chạy `python -m playwright install chromium` rồi chọn Chromium trong trang Cài đặt.

## Sử dụng

Giao diện chạy trong cửa sổ riêng bằng Edge WebView2 (có sẵn trên Windows 10/11). Chỉ mở được 1 cửa sổ app cùng lúc.
Có chế độ **sáng / tối / theo Windows** (nút ở góc dưới thanh bên, hoặc trang Cài đặt) và trang **Hướng dẫn** ngay trong app.

Nhấp đúp `run.bat`, hoặc:
```bash
python -m rewards_bot
```

1. Trang **Tài khoản**: bấm **Thêm tài khoản** cho mỗi tài khoản Microsoft.
2. Bấm **Đăng nhập** ở dòng tài khoản đó. Cửa sổ mở 2 tab: đăng nhập ở tab Rewards, rồi kiểm tra tab **bing.com**
   cũng là **cùng tài khoản** (góc phải). Xong thì **đóng cửa sổ** (chỉ làm 1 lần).
3. Bấm **Kiểm tra** ở dòng tài khoản: bot tự chẩn đoán (không search). Kết quả từng mục (OK/WARN/FAIL kèm cách sửa)
   hiện ở trang **Nhật ký**.
4. Chọn việc bot sẽ làm ở mục "Việc bot sẽ làm khi chạy", rồi bấm **Chạy** (1 tài khoản) hoặc **Chạy tất cả**.
   Ô "Số tài khoản chạy cùng lúc" giới hạn số cửa sổ chạy song song. **Dừng tất cả** để dừng.

### Trang Tổng quan
- Chọn tài khoản ở hàng trên cùng. Khối bên trái là số điểm hiện có, điểm hôm nay, tháng này và trọn đời.
- **Thẻ đóng dấu hôm nay**: mỗi task có điểm (search PC/Mobile, Daily Set, Keep earning) là một con dấu dùng ảnh
  từ trang Rewards; làm xong thì dấu sáng lên. Bên dưới là tiến độ search PC/Mobile.
- Biểu đồ điểm mỗi ngày (PC / Mobile / Offers, 14 ngày) và số điểm hiện có (30 ngày); rê chuột để xem số liệu.
- **Task hôm nay** gọn: mỗi việc một dòng (icon, tên, nhãn `10/10`), việc chưa xong lên trước, nhóm có vòng tiến độ,
  công tắc "Ẩn việc đã xong". Search PC/Mobile không lặp lại (đã có thanh tiến độ phía trên).
- **Số liệu**: 4 ô (hôm nay, trung bình 7 ngày, chuỗi ngày đủ điểm search, tháng này so với cùng kỳ tháng trước),
  **lịch nhiệt 12 tuần** (độ đều đặn), **nguồn điểm 30 ngày** (PC / Mobile / thẻ), và **so sánh tài khoản** khi có từ 2
  tài khoản.
- **Tiếng Việt / English**: nút VI / EN ở thanh bên (hoặc Cài đặt). Dòng nhật ký do bot ghi vẫn là tiếng Việt.
- **Làm mới** chỉ đọc điểm từ Rewards (chạy ẩn), không làm task.
- **Mục tiêu đổi quà** (trong khối điểm): đặt món muốn đổi và số điểm cần, app hiện thanh tiến độ và dự kiến số ngày
  còn lại, tính theo trung bình điểm/ngày của 14 ngày gần nhất trong Lịch sử (bỏ hôm nay vì chưa hết ngày).
- **Kiểm tra** (tự chẩn đoán, không search): đăng nhập Rewards, Points breakdown, thẻ Daily Set, bing.com có đúng
  tài khoản không (desktop và mobile), profile có bị cửa sổ khác giữ không, proxy. Cũng chạy được bằng
  `python -m rewards_bot --check`.
- Trang **Lịch sử**: mỗi ngày, mỗi tài khoản một dòng: điểm trong ngày, search PC/Mobile, điểm thẻ & hoạt động, và
  các việc **còn thiếu** (vd Edge – Minutes 0/30, Mobile App check-in, thẻ chưa được ghi nhận).

### Cách bot mở trình duyệt
Ở chế độ **Cửa sổ riêng**, app tự mở Edge như một trình duyệt bình thường (chỉ vài cờ cần thiết, không có cờ tự động hóa,
`navigator.webdriver` = false) rồi điều khiển qua một cổng debug **chỉ trên 127.0.0.1**, do Edge tự chọn và đóng cùng
trình duyệt, giống cách Selenium làm. Mở bằng cờ tự động hóa của Playwright thì Bing từ chối Visual Search.
Ý tưởng này lấy từ [AutoRewarder](https://github.com/safarsin/AutoRewarder) (MIT).

### Bot tự bảo vệ khi chạy
- Trước khi search, đối chiếu điểm trên bing.com với Rewards; **sai tài khoản thì không search** (để không cộng nhầm).
- Cứ 3 lượt search đọc lại điểm; **6 lượt liên tiếp không được cộng thì dừng** loại search đó và ghi lý do.
- **Search Mobile** chạy trong một tab giả lập điện thoại Android (UA và client hints khớp đúng phiên bản Edge đang
  chạy). Trước khi sang tab mobile, bot xóa cookie phiên search của Bing (`_Rwho`, `_SS`, `_EDGE_S`; không đụng cookie
  đăng nhập): Bing đánh dấu cả phiên là desktop (`_Rwho=u=d`) sau lượt search PC / lần mở bing.com đầu tiên, nếu
  không xóa thì search Mobile bị tính là PC và không được điểm.
- Thẻ Daily Set / Keep earning được bấm đúng vị trí (kể cả 2 thẻ trùng tên); thẻ nào làm xong mà chưa được ghi
  nhận thì **làm lại 1 lần**, vẫn chưa được thì liệt kê trong nhật ký.
- Trang Rewards tải chậm / treo thì **tải lại 1 lần** trước khi báo lỗi.
- **Profile Edge cố định**: một thư mục tài khoản có thể chứa nhiều profile Edge (Default, Profile 1...), mỗi cái đăng
  nhập trình duyệt bằng tài khoản khác. Lần mở đầu tiên bot ghim profile đang dùng vào `rewards_bot_profile.txt` trong
  thư mục đó và từ đó luôn mở đúng profile ấy. **Kiểm tra** báo nếu trong thư mục còn profile khác.
- **Tự đăng nhập lại** (không bắt buộc): trong hộp **Sửa** tài khoản, nhập email + mật khẩu Microsoft. Khi phiên hết
  hạn, bot tự điền form đăng nhập rồi chạy tiếp. Nếu Microsoft hỏi mã xác minh, Authenticator hay CAPTCHA, bot
  **dừng lại** để bạn bấm **Đăng nhập** và tự làm (bot không vượt qua các bước đó).
- Nhật ký lưu ở `data/logs/<ngày>.log` (giữ 14 ngày) – gửi file này khi cần báo lỗi.
- Tài khoản có thư mục phiên đăng nhập cố định: đổi tên không phải đăng nhập lại.
- Số liệu PC/Mobile lấy từ hộp **Points breakdown** trên trang Earn. Lịch sử lưu ở `data/points_history.json`,
  dữ liệu lần cuối ở `data/dashboard.json`.

### Task thêm
- **Quests**: quest nhiều bước ở trang Earn ("5/6 tasks"), có công tắc riêng, chạy sau Daily Set. Trang quest liệt kê
  các bước ở mục "Activities"; bước làm được trên trình duyệt có link. Bước khóa sau app Microsoft Rewards trên máy tính
  hoặc app điện thoại thì bỏ qua (ghi lý do vào nhật ký); bước làm 2 lần không được ghi nhận cũng bỏ qua.
- **Visual Search**: mỗi ngày 1 lượt: lấy ngẫu nhiên 1 ảnh trên Bing Images, bấm nút camera ("Search using an image")
  và tải ảnh đó lên, rồi đọc lại Rewards xem đã được ghi nhận chưa. Bật/tắt ở mục "Việc bot sẽ làm khi chạy".
  Bing chặn ("Unable to process this search") khi một tài khoản thử nhiều lần trong ngày, nên bot thử **tối đa 4 lần
  mỗi ngày** (cộng dồn các lượt chạy, lưu ở `data/visual_tries.json`).
- **Browse**: lướt các trang tin tức/kiến thức tối đa N phút, cuộn trang và đi theo link nội bộ, nhắm tới
  "Edge – Minutes" (Edge Browsing Streak). Mặc định **tắt**. Edge tự đo thời gian dùng trình duyệt rồi báo cho Rewards.
  Làm được, nhưng thường phải **chạy lại 3–4 lượt** trong ngày mới đủ 30/30 (khi đó nên tắt "Tự dừng"). Vì vậy Browse **tự đo**: cứ 10 phút đọc lại Edge – Minutes,
  ghi vào nhật ký `Edge – Minutes: 0 → 12/30 sau 10 phút (chạy ẩn)`, dừng khi đã đủ hoặc khi **20 phút không tăng**
  (tắt bằng công tắc "Browse tự dừng khi không được tính phút" để luôn lướt đủ N phút),
  và bỏ qua nếu hôm nay đã đủ hoặc tài khoản không có mục này. Xem nhật ký vài ngày để biết chạy ẩn hay hiện cửa sổ mới
  được tính.
- Số lượt và số phút chỉnh trong trang Cài đặt.

### Câu search
Bot tự sinh câu search từ 21 lĩnh vực (khoảng 2.600 câu tiếng Anh, trung bình ~8 từ, câu nào cũng có nghĩa), ví dụ:
*how to set up nginx as a reverse proxy with ssl using lets encrypt*, *league of legends wave management guide for beginners*.

- **IT** chia 6 mảng: Server & Mạng (nginx, load balancing, BGP…), DevOps & Cloud (docker, kubernetes, kafka…),
  IoT & Phần cứng (ESP32, MQTT, Zigbee…), Bảo mật, Lập trình (ngôn ngữ, cấu trúc dữ liệu & giải thuật), Dữ liệu & AI.
- **Game**: Roblox, League of Legends/TFT, Fortnite, Minecraft, Valorant, CS2, Dota 2, Genshin, Liên Quân…
- **Học thuật**: Toán, Vật lý & Vũ trụ, Hóa & Sinh, Kinh tế & Tài chính; cùng các mảng đời sống (sức khỏe, ẩm thực,
  du lịch, lịch sử, thể thao, giải trí, ngoại ngữ, nhà cửa, xe, thiên nhiên).

Không trùng nhau, hai câu liền nhau không cùng lĩnh vực, các tài khoản không tìm cùng một câu, và câu đã dùng không
lặp lại trong N ngày (lưu ở `data/search_history.json`). Muốn thêm câu: sửa `rewards_bot/search/catalog.py`.

### Hai cách chạy nhiều cửa sổ
- **Cửa sổ riêng** (khuyên dùng): mỗi tài khoản có thư mục `data/profiles/<tên>` riêng, mỗi tài khoản mở 1 cửa sổ.
- **Gắn vào Edge đang mở**: tự mở Edge với cổng debug, mỗi cửa sổ một cổng và một thư mục:
  ```bash
  msedge.exe --remote-debugging-port=9222 --user-data-dir="C:\EdgeRewards1"
  ```
  ```bash
  msedge.exe --remote-debugging-port=9223 --user-data-dir="C:\EdgeRewards2"
  ```
  Đăng nhập trong từng cửa sổ, rồi thêm tài khoản chế độ "Gắn vào Edge đang mở" với cổng 9222 hoặc 9223.
  (Edge không cho debug trên profile mặc định, nên phải dùng `--user-data-dir` riêng.)


## Bảo mật

- **Thư mục `data/`** (phiên đăng nhập, cookie Microsoft) được khóa quyền ngay lần chạy đầu: chỉ tài khoản Windows
  của bạn và SYSTEM đọc được. Thư mục này không bao giờ được commit lên git.
- **Proxy**: trình duyệt của bot chạy với `--no-proxy-server`, bỏ qua proxy hệ thống và file PAC. Nếu máy đang bật
  proxy, nhật ký sẽ ghi lại để bạn biết. Muốn đi qua proxy (mạng công ty), tắt tùy chọn này trong trang Cài đặt.
- **Mật khẩu tự đăng nhập** lưu ở `data/credentials.json`, mã hóa bằng Windows DPAPI: chỉ tài khoản Windows này
  trên máy này giải mã được (copy file sang máy khác là vô dụng), giao diện không bao giờ nhận lại mật khẩu, nhật ký không
  bao giờ ghi mật khẩu. Không có DPAPI (Linux) thì tính năng tắt, không lưu dạng chữ thường. Xóa tài khoản là xóa luôn.
- **HTTPS** luôn được kiểm tra chứng chỉ, nên proxy chen giữa dùng chứng chỉ giả sẽ bị chặn.
- **Giao diện** có Content-Security-Policy: chỉ chạy script của app, chỉ tải ảnh từ bing.com. Dữ liệu lấy từ trang
  Rewards luôn được escape. Mọi giá trị giao diện gửi xuống Python (cài đặt, tên tài khoản, cổng, lệnh) đều được kiểm tra.
- **Cổng debug khi bot đang chạy**: ở chế độ Cửa sổ riêng, Edge mở một cổng debug ngẫu nhiên chỉ trên `127.0.0.1` và
  đóng khi trình duyệt đóng. Trong lúc đó, chương trình khác **trên cùng máy** có thể điều khiển cửa sổ Edge đã đăng
  nhập đó (mạng ngoài thì không). Mọi bot dùng CDP/Selenium đều vậy. Đừng chạy bot trên máy dùng chung với người khác.
- **Chế độ Gắn vào Edge đang mở**: cổng debug cho phép mọi chương trình trên máy điều khiển Edge. Bot chỉ kết nối qua
  `127.0.0.1` và từ chối chạy nếu cổng bị mở ra mạng LAN. Chỉ bật Edge debug khi cần chạy bot.
- **Cập nhật tự động** chỉ tải file từ máy chủ của GitHub (HTTPS), so mã SHA-256 với file `.sha256` của bản phát
  hành, kiểm tra nội dung zip (không ghi ra ngoài thư mục app, không đụng `data/`) rồi mới cài. SHA-256 bảo vệ khỏi file
  hỏng hoặc bị sửa trên đường tải; nó không thay được chữ ký số, nên ai cũng có thể tự build từ mã nguồn nếu muốn chắc chắn.
- Giới hạn: phần mềm độc hại chạy dưới chính tài khoản Windows của bạn vẫn có thể đọc dữ liệu của bạn. Hãy giữ
  Windows và phần mềm diệt virus cập nhật.

## Chạy trên Linux

Bot (search, Daily Set, Visual Search…) và chế độ không giao diện chạy được trên Linux. Cần:

1. Python 3.10+ và các gói: `pip install -r requirements.txt`
2. Một trình duyệt dòng Chromium: **Microsoft Edge** (`microsoft-edge-stable`, nên dùng), Google Chrome hoặc Chromium.
   Bot tự tìm theo tên lệnh trên PATH hoặc `/opt/microsoft/msedge`. Dùng Chrome/Chromium thì chọn trong trang Cài đặt
   (hoặc sửa `"browser_channel"` trong `data/settings.json`).
3. Giao diện (tùy chọn) cần thêm bộ hiển thị web cho pywebview, một trong hai:
   - GTK: `sudo apt install python3-gi gir1.2-webkit2-4.1` (Debian/Ubuntu), hoặc
   - Qt: `pip install "pywebview[qt]"`

```bash
./run.sh
```
```bash
./run.sh --run-all --headless
```

Khác với Windows: không khóa quyền thư mục `data/` (tự `chmod 700 data` nếu cần), không đọc proxy hệ thống, và
font Bahnschrift của giao diện Cyberpunk được thay bằng font dự phòng. Chạy hằng ngày bằng cron, ví dụ
`30 7 * * * cd /đường/dẫn/rewards-bot && ./run.sh --run-all --headless`.

## Chạy tự động hằng ngày (không mở giao diện)

```bash
python -m rewards_bot --run-all --headless
```
Đặt lệnh này trong Windows Task Scheduler, với thư mục bắt đầu là thư mục dự án (hoặc dùng `run.bat --run-all --headless`).
Bản .exe: lệnh là `C:\RewardsBot\RewardsBot.exe --run-all --headless`.

## Cập nhật

- **Bản .exe:** mở app thì app tự hỏi GitHub có bản mới không (tắt được trong Cài đặt). Có bản mới thì hiện thanh báo ở
  trên cùng: **Tải và cập nhật**, rồi **Khởi động lại để cập nhật**. App đóng, chép đè file mới rồi tự mở lại; thư mục
  `data\` không bao giờ bị đụng tới. Kết quả ghi ở `data\update\update.log`.
- Bản cập nhật chỉ được cài khi mã SHA-256 của file zip khớp file `.sha256` đi kèm bản phát hành.
- **Bản mã nguồn:** `git pull`.
- App bị lỗi khi mở (bản .exe): chi tiết ghi ở `data\crash.log`.

### Phát hành bản mới (người phát triển)
1. Tăng `__version__` trong `rewards_bot/__init__.py`, commit.
2. `git tag v<phiên bản>` rồi `git push origin v<phiên bản>`. GitHub Actions (`.github/workflows/release.yml`) chạy test,
   build `.exe` trên Windows và tạo Release kèm file zip và file `.sha256` của nó.
3. Build thử trên máy: `python packaging/build_exe.py` ra `dist/RewardsBot/RewardsBot.exe` và
   `dist/RewardsBot-<phiên bản>-win64.zip`.

## Cấu trúc

```
rewards-bot/
├── rewards_bot/
│   ├── __main__.py         # điểm vào: python -m rewards_bot [--run-all | --check]
│   ├── cli.py              # chạy không giao diện
│   ├── core/
│   │   ├── bot.py          # bot cho 1 tài khoản: task, search, kiểm tra (diagnose)
│   │   ├── rewards_page.py # đọc trang Rewards (điểm, task, icon, Points breakdown)
│   │   ├── runner.py       # chạy nhiều tài khoản song song + ghi log ra file
│   │   ├── edge_launcher.py # mở Edge "thường" + cổng debug cục bộ để Playwright gắn vào
│   │   ├── browser.py      # phát hiện trình duyệt đang giữ profile
│   │   ├── security.py     # khóa quyền data/, proxy, cổng debug
│   │   ├── instance.py     # chỉ 1 cửa sổ app chạy cùng lúc
│   │   ├── credentials.py  # mật khẩu tự đăng nhập, mã hóa DPAPI
│   │   ├── updater.py      # kiểm tra + cài bản mới từ GitHub Releases
│   │   └── config.py       # cài đặt, tài khoản, đọc/ghi file an toàn
│   ├── search/             # catalog.py (danh mục câu search) + bank.py (chia câu không trùng)
│   └── ui/                 # webapp.py (pywebview) + web/ (index.html, style.css, app.js, theme.js)
│                           #   web/vendor/: Tabler, Tabler Icons, ApexCharts (MIT, lưu sẵn, không tải từ mạng)
├── packaging/              # build bản .exe (PyInstaller): build_exe.py, RewardsBot.spec, launcher.py
├── .github/workflows/      # release.yml: đẩy tag v* -> build .exe + tạo GitHub Release
├── tests/                  # pytest: logic, dữ liệu, giao diện
├── data/                   # tự tạo khi chạy (không commit)
├── run.bat / run.sh        # mở app (Windows / Linux)
├── check.bat / check.sh    # chạy test
├── CLAUDE.md / AGENTS.md   # ghi chú cho trợ lý AI viết code (lệnh, cấu trúc, các lỗi đã tìm ra)
├── requirements.txt
└── requirements-dev.txt
```

## Phát triển

```bash
pip install -r requirements-dev.txt
```
Chạy `check.bat` (hoặc `python -m pytest -q tests`) trước mỗi lần commit.

## Giấy phép

Mã nguồn phát hành theo giấy phép [MIT](LICENSE). Các thư viện đi kèm trong `rewards_bot/ui/web/vendor/` giữ giấy phép
riêng (file LICENSE trong từng thư mục): Tabler và Tabler Icons (MIT), ApexCharts 3.54 (MIT), Fluent Emoji (MIT),
font Chakra Petch (SIL OFL 1.1). "Microsoft", "Bing", "Edge" và "Microsoft Rewards" là thương hiệu của Microsoft.
