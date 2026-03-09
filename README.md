# New Book Request

**Penanggung Jawab Fitur:**  
**Naurah Iradya Kurniawan – 2306245900**

Fitur New Book Request merupakan fitur pada sistem NASA Library yang memungkinkan siswa dan guru untuk mengajukan usulan buku baru secara terstruktur melalui sistem. Fitur ini dirancang untuk melibatkan pengguna secara aktif dalam pengembangan koleksi perpustakaan agar koleksi yang tersedia selaras dengan kebutuhan akademik dan minat baca pengguna.

**Deskripsi Fitur**

New Book Request mendukung proses pengelolaan usulan buku mulai dari pengajuan oleh siswa dan guru, pemantauan status usulan, hingga proses peninjauan oleh petugas perpustakaan. Seluruh proses dilakukan secara digital untuk meningkatkan transparansi, efisiensi, serta dokumentasi pengambilan keputusan dalam pengadaan buku.

**Fitur Utama**

1. **Pengajuan Usulan Buku oleh Siswa dan Guru**
   1. Pengguna mengajukan usulan buku dengan mengisi informasi judul, penulis, penerbit, kategori (opsional), serta alasan pengajuan.
   2. Sistem melakukan validasi data dan menyimpan usulan dengan status *Menunggu*.
   3. Pengguna memperoleh notifikasi bahwa usulan telah berhasil dikirim dan akan ditinjau oleh petugas perpustakaan.

2. **Riwayat Usulan Buku**
   1. Pengguna dapat melihat riwayat usulan buku yang pernah diajukan.
   2. Sistem menampilkan status usulan berupa *Menunggu*, *Disetujui*, atau *Ditolak*.
   3. Apabila usulan ditolak, pengguna dapat melihat catatan penolakan sebagai bentuk transparansi.
   4. Sistem menampilkan ringkasan jumlah usulan berdasarkan status untuk memudahkan pemantauan.

3. **Review Usulan Buku oleh Petugas**
   1. Petugas perpustakaan dapat melihat daftar usulan buku yang masih menunggu peninjauan.
   2. Petugas memiliki kewenangan untuk menyetujui atau menolak usulan buku.
   3. Pada usulan yang ditolak, petugas wajib memberikan alasan penolakan.
   4. Sistem mencatat aktivitas peninjauan dan mengirimkan notifikasi kepada pengaju usulan.

**Business Value**

1. Mendorong partisipasi aktif siswa dan guru dalam pengembangan koleksi perpustakaan.  
2. Meningkatkan relevansi koleksi buku dengan kebutuhan dan minat pengguna.  
3. Menyediakan transparansi status usulan buku secara sistematis.  
4. Membantu petugas perpustakaan dalam mengelola proses pengadaan buku secara efisien dan terdokumentasi.  
# Peminjaman & Pengembalian Buku

Sistem Informasi Perpustakaan & Platform Literasi Digital
Sistem Informasi Perpustakaan & Platform Literasi Digital
SMAN 61 Jakarta

Fitur Rekomendasi Buku membantu siswa dan guru menemukan buku yang menarik dan relevan berdasarkan data peminjaman terbanyak di perpustakaan. Fitur ini bertujuan untuk meningkatkan minat baca dan mempermudah pengguna dalam memilih buku dari koleksi yang besar.

### Deskripsi Fitur
Sistem secara otomatis menganalisis data peminjaman buku dan menampilkan daftar buku yang paling sering dipinjam dalam periode tertentu. Rekomendasi ditampilkan pada halaman utama atau halaman pencarian buku sehingga mudah diakses oleh pengguna.

### Fitur Utama
- Perhitungan jumlah peminjaman setiap buku
- Menampilkan daftar Top 5 atau Top 10 buku terpopuler
- Rekomendasi ditampilkan di homepage
- Akses langsung ke detail buku dari daftar rekomendasi
- Informasi ketersediaan buku secara real-time

### Business Value
- Membantu pengguna menemukan buku yang banyak diminati
- Meningkatkan frekuensi peminjaman buku
- Mendukung program peningkatan minat baca sekolah
- Memberikan insight tren bacaan populer di lingkungan sekolah
Fitur ini memungkinkan anggota melakukan peminjaman buku secara digital, sehingga proses menjadi lebih terstruktur, transparan, serta meminimalisir kesalahan pencatatan manual.

---

## 1. Peminjaman Buku

### 1.1 Tujuan

Fitur ini memungkinkan anggota melakukan peminjaman buku secara digital, sehingga proses menjadi lebih terstruktur, transparan, serta meminimalisir kesalahan pencatatan manual.

### 1.2 Spesifikasi API

**Endpoint:**
- POST `/api/loans` - Membuat pengajuan peminjaman

**Request Body:**
- ID anggota
- ID buku

**Fitur Sistem:**
- Sistem memvalidasi bahwa status buku adalah "Available"
- Jika buku tersedia, sistem mengubah status buku menjadi "Booked"
- Sistem menyimpan data transaksi dengan status "Menunggu Persetujuan"
- Sistem menetapkan durasi peminjaman default 7 hari setelah disetujui
- Jika buku tidak tersedia, sistem mengembalikan pesan "Buku tidak tersedia"

**Setelah Disetujui Petugas:**
- Sistem mengubah status transaksi menjadi "Borrowed"
- Sistem mencatat tanggal jatuh tempo sesuai input user (default = 7 hari dari tanggal persetujuan)
- Sistem menyimpan histori transaksi peminjaman anggota

### 1.3 Halaman Katalog Buku

**Komponen Halaman:**
- Menampilkan daftar buku beserta statusnya (Available/Booked/Borrowed)
- Tombol "Pinjam Buku" pada buku yang berstatus Available
- Tombol hanya aktif jika buku tersedia

**Perilaku Sistem:**
- Setelah tombol ditekan, sistem menampilkan modal berisi field input durasi peminjaman (default = 7 hari) dan tombol submit
- Muncul notifikasi "Pengajuan peminjaman berhasil"
- Status buku berubah menjadi "Booked"
- Anggota dapat melihat status peminjaman di halaman Riwayat
- Jika buku tidak tersedia, sistem menampilkan pesan error yang sesuai

---

## 2. Pengajuan Perpanjangan Peminjaman

### 2.1 Tujuan

Fitur ini memungkinkan anggota memperpanjang masa pinjam tanpa harus datang langsung ke perpustakaan, sehingga meningkatkan efisiensi layanan dan kenyamanan pengguna.

### 2.2 Spesifikasi API

**Endpoint:**
- POST `/api/loans/{id}/extend` - Mengajukan perpanjangan

**Fitur Sistem:**
- Sistem memvalidasi bahwa status transaksi adalah "Borrowed"
- Status berubah menjadi "Menunggu Persetujuan Perpanjangan"
- Petugas dapat menyetujui atau menolak pengajuan
- Jika disetujui, sistem memperbarui tanggal jatuh tempo
- Jika ditolak, sistem mengembalikan status menjadi "Borrowed"

### 2.3 Antarmuka Pengguna

**Komponen Halaman:**
- Terdapat tombol "Ajukan Perpanjangan" pada transaksi aktif
- Tombol hanya muncul jika status adalah Borrowed

**Perilaku Sistem:**
- Sistem menampilkan status pengajuan (Menunggu/Disetujui/Ditolak)
- Jika disetujui, tanggal jatuh tempo diperbarui otomatis

---

## 3. Riwayat Peminjaman Anggota

### 3.1 Tujuan

Fitur ini memungkinkan anggota dan petugas melihat seluruh histori transaksi secara transparan, sehingga memudahkan monitoring dan pertanggungjawaban penggunaan buku.

### 3.2 Spesifikasi API

**Endpoint:**
- GET `/api/loans` - Mengambil riwayat peminjaman

**Fitur Sistem:**
- Anggota hanya dapat melihat riwayat miliknya sendiri
- Petugas dapat melihat seluruh riwayat anggota
- Data menampilkan status, tanggal pinjam, tanggal jatuh tempo, dan tanggal kembali

### 3.3 Halaman Riwayat

**Komponen Halaman:**
- Menampilkan tabel transaksi
- Data dapat difilter berdasarkan status
- Status ditampilkan dengan label berbeda (Booked/Borrowed/Returned)

**Perilaku Sistem:**
- Jika belum terdapat riwayat peminjaman, sistem menampilkan pesan "Belum ada riwayat peminjaman buku"

---

## 4. Monitoring Buku Belum Dikembalikan

### 4.1 Tujuan

Fitur ini memungkinkan petugas memantau seluruh buku yang masih dipinjam beserta tanggal jatuh tempo, sehingga memudahkan pengawasan dan tindak lanjut.

### 4.2 Spesifikasi API

**Endpoint:**
- GET `/api/loans/active` - Mengambil daftar peminjaman aktif

**Fitur Sistem:**
- Sistem hanya menampilkan transaksi dengan status "Borrowed"
- Sistem menampilkan informasi keterlambatan berdasarkan tanggal jatuh tempo
- Data dapat difilter berdasarkan rentang waktu

### 4.3 Halaman Monitoring

**Komponen Halaman:**
- Menampilkan daftar buku yang sedang dipinjam
- Terdapat indikator jika melewati tanggal jatuh tempo
- Petugas dapat mencari berdasarkan nama anggota atau judul buku

---

## 5. Pemrosesan Peminjaman dan Pengembalian Buku

### 5.1 Tujuan

Fitur ini memungkinkan petugas memproses persetujuan peminjaman dan pengembalian buku secara terkontrol, sehingga seluruh pergerakan buku terdokumentasi dengan baik.

### 5.2 Spesifikasi API

**Endpoint Persetujuan Peminjaman:**
- PUT `/api/loans/{id}/approve` - Menyetujui peminjaman

**Fitur:**
- Jika disetujui, status transaksi menjadi "Borrowed"
- Status buku berubah menjadi "Borrowed"

**Endpoint Penolakan Peminjaman:**
- PUT `/api/loans/{id}/reject` - Menolak peminjaman

**Endpoint Pengembalian:**
- PUT `/api/loans/{id}/return` - Memproses pengembalian

**Fitur:**
- Sistem mencatat tanggal pengembalian
- Sistem mengubah status transaksi menjadi "Returned"
- Status buku berubah menjadi "Available"
- Jika buku rusak atau hilang, sistem mengubah status buku menjadi "Rusak" atau "Hilang"
- Sistem mencatat kasus kehilangan atau kerusakan

### 5.3 Antarmuka Petugas

**Komponen Halaman:**
- Petugas dapat melihat daftar pengajuan peminjaman
- Tersedia tombol "Approve" dan "Reject"
- Petugas dapat mencari transaksi berdasarkan nama anggota
- Pada proses pengembalian, petugas dapat memilih kondisi buku (Baik/Rusak/Hilang)

**Perilaku Sistem:**
- Jika belum terdapat transaksi yang akan diproses, sistem menampilkan pesan "Tidak ada peminjaman atau pengembalian buku saat ini"

---

## 6. Status Peminjaman

| Status | Deskripsi |
|--------|-----------|
| Available | Buku dapat dipinjam |
| Booked | Buku sudah dipesan (menunggu persetujuan) |
| Borrowed | Buku sedang dipinjam |
| Returned | Buku telah dikembalikan |
| Rusak | Buku dalam kondisi rusak |
| Hilang | Buku hilang |

---

## 7. Status Transaksi Peminjaman

While working on a feature:

* Only modify files related to your feature
* Do not refactor or touch unrelated code
* Follow Django layered architecture (Controller → Service → Repository)

If shared changes are needed (e.g. config), discuss with the team first.

---

### Step 3 – Commit Rules

Commit **small, logical changes** with clear messages.

**Commit message convention:**

```
feat: add book management API
fix: correct fine calculation logic
refactor: simplify service layer
chore: update docker configuration
```

Example:

```bash
git add .
git commit -m "feat: implement borrow book API"
git push origin feature/<feature-name>
```

---

### Step 4 – Create Merge Request (MR)

On GitLab:

* Source branch: `feature/<feature-name>`
* Target branch: `develop`
* Assign **at least one reviewer**
* Add a short description of what was implemented

**Before creating MR, ensure:**

* Application builds successfully
* No unnecessary files are committed

---

### Step 5 – Review & Merge

Reviewer responsibilities:

* Verify separation of layers
* Ensure no breaking changes

If approved, **merge into `develop`**.

---

### Step 6 – Merge to Main (Milestone Only)

Merge `develop` into `main` only when:

* A milestone is completed
* System is ready for demo or evaluation

```bash
git checkout main
git merge develop
git push origin main
```

---

## 5. Daily Development Workflow (Mandatory)

Start a new feature:

```bash
git checkout develop
git pull origin develop
git checkout feature/<your-feature>
```

Finish a feature:

```bash
git push origin feature/<feature-name>
# then create MR to develop
```

This ensures your branch stays updated and prevents large merge conflicts.

| Peran | Meminjam | Melihat Riwayat Sendiri | Melihat Semua Riwayat | Memproses Peminjaman | Monitoring |
|-------|----------|------------------------|----------------------|---------------------|------------|
| Siswa | ✓ | ✓ | ✗ | ✗ | ✗ |
| Pustakawan | ✗ | ✗ | ✓ | ✓ | ✓ |
| Guru | ✗ | ✗ | ✓ | ✗ | ✗ |
| Admin | ✗ | ✗ | ✓ | ✓ | ✓ |
