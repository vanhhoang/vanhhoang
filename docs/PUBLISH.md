# Bước cuối: lấy đủ contributions và cập nhật profile

Workflow hiện yêu cầu token của chính tài khoản `vanhhoang` để đọc contributions mà bạn thấy khi đăng nhập, gồm contributions private/internal được GitHub cho phép tài khoản truy cập. Token mặc định của workflow trước đó chỉ trả về 5 contributions, trong khi ảnh bạn đối chiếu hiển thị 966. Bộ thu thập vẫn giữ khoảng cố định 365 ngày.

## 1. Tạo token đọc thông tin tài khoản

Mở [Personal access token (classic)](https://github.com/settings/tokens/new) khi đăng nhập tài khoản `vanhhoang`:

1. Đặt tên, ví dụ `profile-contributions`, và chọn ngày hết hạn.
2. Chọn scope **read:user**.
3. Chọn **Generate token** và sao chép giá trị để lưu vào secret ở bước tiếp theo.

Quyền `read:user` được GitHub nêu cho contributions trong private/internal repositories ở [ContributionsCollection](https://docs.github.com/en/graphql/reference/users#contributionscollection). Token này dùng cho truy vấn GraphQL tổng hợp contributions và đọc thông tin tài khoản qua `GET /user`, gồm số followers/following khi profile đang private. Không gửi giá trị token vào chat hoặc ghi vào code.

## 2. Thêm repository secret

Mở [New repository secret](https://github.com/vanhhoang/vanhhoang/settings/secrets/actions/new):

- **Name:** `PROFILE_TOKEN`
- **Secret:** giá trị token vừa tạo.
- Chọn **Add secret**.

Dashboard sẽ xuất bản số lượng contributions theo ngày trong ảnh README. Không truy vấn tên hoặc nội dung repository private. Token mặc định `GITHUB_TOKEN` vẫn dùng cho thông tin công khai và commit kết quả; `PROFILE_TOKEN` đọc contributions và thông tin của chính tài khoản. Giữ scope `read:user`; không cần thêm `user:follow` để hiển thị hai chỉ số followers/following.

## 3. Đẩy commit đã chuẩn bị

```sh
cd /Users/hoangvietanh/Documents/vanhhoang
git push origin master
```

Thay đổi trong `scripts/` và workflow sẽ kích hoạt lần làm mới đầu tiên. Các lần tiếp theo chạy vào phút 17 mỗi giờ.

Nếu bạn thêm secret sau khi đã push, mở [Actions → Refresh terminal profile](https://github.com/vanhhoang/vanhhoang/actions/workflows/update-profile.yml), chọn **Run workflow → master → Run workflow**. Việc thêm secret không tự kích hoạt một lần chạy mới.

## Kiểm tra kết quả

Sau khi job thành công:

- Mở [profile-data.json](https://github.com/vanhhoang/vanhhoang/blob/master/assets/profile-data.json): `calendar.visibility` phải là `owner-authenticated`; tổng phải bằng tổng các `count` theo ngày.
- Kiểm tra phần heatmap và dòng **LAST SYNC** trên [profile](https://github.com/vanhhoang).
- Nếu token thiếu, sai tài khoản, thiếu quyền hoặc API lỗi, workflow dừng và giữ bản thành công trước đó. Không dùng lịch công khai thưa dữ liệu để thay thế lịch của chủ tài khoản.

Ảnh mẫu và dữ liệu cũ có thể vẫn hiện trong lúc chưa cấu hình token hoặc do GitHub cache ảnh. Số 966 trong ảnh dùng để đối chiếu; chương trình luôn lấy số thực từ API, không điền sẵn số đó.

[Chi tiết dữ liệu và bảo trì](design.md) · [Bản xem thử](previews/README.md)
