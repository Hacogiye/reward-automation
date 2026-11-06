"use strict";
// Chạy trước khi vẽ trang: đặt sáng/tối theo Windows để không bị nháy trắng. app.js áp lại theo cài đặt sau khi khởi động.
(function () {
  const dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.setAttribute("data-bs-theme", dark ? "dark" : "light");
  try {  // thanh bên thu gọn từ lần trước: đặt ngay để không bị nháy rộng rồi mới thu
    if (localStorage.getItem("sideCollapsed") === "true") document.documentElement.classList.add("side-collapsed");
  } catch { /* bỏ qua */ }
})();
