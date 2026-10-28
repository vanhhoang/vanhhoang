# Bước cuối: đưa profile lên GitHub

Bản cập nhật đã giữ bố cục terminal, bổ sung nền trong suốt với hai bộ màu sáng/tối, dữ liệu GitHub thật và workflow tự làm mới mỗi giờ. Mã nguồn, dữ liệu và kiểm tra đã được chuẩn bị trong commit local.

Mở Terminal trên máy của bạn và chạy:

```sh
cd /Users/hoangvietanh/Documents/vanhhoang
git push origin master
```

Lệnh này công bố commit đã chuẩn bị lên repository profile. Thay đổi trong `scripts/` và workflow sẽ tự kích hoạt lần làm mới đầu tiên. Các lần tiếp theo chạy vào phút 17 mỗi giờ, hoặc khi bạn chọn **Run workflow**.

Theo dõi tại [Actions → Refresh terminal profile](https://github.com/vanhhoang/vanhhoang/actions/workflows/update-profile.yml). Khi job hoàn tất, mở [profile GitHub](https://github.com/vanhhoang) và kiểm tra dòng **LAST SYNC** trong dashboard.

Workflow dùng token có sẵn của GitHub Actions; không cần thêm secret cho dữ liệu công khai. Chu kỳ làm mới là mỗi giờ và ảnh có thể hiển thị chậm hơn do cache của GitHub.

Nếu remote có thêm commit trong lúc bạn chưa push, Git có thể yêu cầu đồng bộ trước. Giữ nguyên kiểm tra này của Git, không dùng force push.

[Chi tiết dữ liệu và bảo trì](design.md) · [Bản xem thử](previews/README.md)
