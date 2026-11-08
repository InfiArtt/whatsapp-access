# WhatsApp Access

WhatsApp Access menampilkan chat WhatsApp Anda dalam jendela sederhana yang dibuat untuk pembaca
layar NVDA. Di sana Anda membaca dan membalas pesan serta mengirim voice note yang jernih, sementara
WhatsApp Web tetap terbuka di Brave, Google Chrome, atau Microsoft Edge. Browser boleh tetap di
belakang, diminimalkan, atau di desktop virtual lain.

Ini cara lain untuk melihat dan memakai WhatsApp, bukan bot. Add-on hanya mengirim apa yang Anda
tulis atau rekam, saat Anda memilih mengirimnya. Add-on tidak pernah membalas atau mengirim pesan
sendiri.

## Dua cara terhubung ke WhatsApp

- **Browser tersembunyi milik add-on** (disarankan). Add-on menjalankan WhatsApp Web di Brave, Google
  Chrome, atau browser Chromium lain versi 120 atau lebih baru, tanpa jendela dan dengan profilnya
  sendiri, jadi browser Anda tidak tersentuh dan tidak ada yang meminta izin. Anda menautkannya sekali ke
  ponsel dengan kode, dan ia muncul di ponsel di Perangkat tertaut. Ia bisa berjalan bersama NVDA, jadi
  pesan baru dibacakan kapan saja. Memakai sekitar 400 sampai 600 MB memori.
- **WhatsApp Web di browser Anda sendiri**, dijelaskan di bawah. Browser Anda meminta izin setiap kali dibuka.

Pertama kali Anda menekan NVDA+Shift+W, add-on menanyakan cara yang Anda inginkan. Anda bisa mengubahnya
di pengaturan NVDA, WhatsApp Access, yang juga punya **Putuskan tautan komputer ini**: keluar dari WhatsApp
dan menghapus apa yang disimpan browser tersembunyi. Menghapus add-on juga menghapusnya.

### Menautkan browser tersembunyi

1. Ketik nomor telepon Anda dengan kode negaranya lalu tekan Enter.
2. Add-on membacakan kode 8 karakter huruf demi huruf, dan menampilkannya di kotak dengan tombol Salin.
3. Di ponsel, buka WhatsApp, lalu Setelan, Perangkat tertaut, Tautkan perangkat, dan pilih
   **Tautkan dengan nomor telepon saja**. Ketik kodenya. Ponsel Anda mungkin juga menampilkan notifikasi.
4. Begitu ponsel menerimanya, add-on mengucapkan "Tertaut" dan membuka chat Anda.

## Yang dibutuhkan untuk WhatsApp Web di browser Anda sendiri

- NVDA 2026.3 atau lebih baru.
- WhatsApp Web terbuka dan sudah masuk di web.whatsapp.com, di Brave, Google Chrome, atau Microsoft Edge.
- Remote debugging dinyalakan di browser itu, cukup sekali:
  1. Buka tab baru dengan Control+T.
  2. Ketik `brave://inspect/#remote-debugging` lalu tekan Enter.
     Di Chrome alamatnya `chrome://inspect/#remote-debugging`, di Edge `edge://inspect/#remote-debugging`.
  3. Centang "Allow remote debugging for this browser instance".

## Cara memakai

Tekan **NVDA+Shift+W** untuk membuka jendela WhatsApp.

Pertama kali setelah browser dibuka, add-on menyambung ke browser. Browser muncul ke depan dan
bertanya "Allow remote debugging?". Fokusnya ada di Cancel: tekan **Shift+Tab**, lalu **Enter**
untuk memilih Allow. Selama add-on tersambung, browser menampilkan bar bahwa browser sedang
dikendalikan perangkat lunak. Itu add-on ini.

### Daftar chat

- Ketik di **Cari chat** (Alt+C) untuk mencari chat berdasarkan nama.
- Di **Daftar chat** (Alt+H), tiap chat menyebut namanya, jumlah pesan yang belum dibaca, dan pesan
  terakhirnya. Tekan **Enter** untuk membukanya.
- **Escape** menutup jendela. WhatsApp Web tetap terbuka, dan pesan baru tetap dibacakan.

### Bagian

Jendela punya bagian, seperti bilah samping WhatsApp: **Chat** (Ctrl+1), **Status** (Ctrl+2),
**Panggilan** (Ctrl+3), dan **Diarsipkan** (Ctrl+4). Ctrl+Tab dan Ctrl+Shift+Tab pindah ke bagian
berikutnya dan sebelumnya. Bagian ini bukan tab: tekan Tab melewati kontrol sebuah bagian untuk sampai
ke daftar **Bagian**, yang menyebut bagian mana yang sedang dibuka; pilih yang lain dengan panah lalu
tekan Enter.

- **Status** menampilkan orang yang membuat status, yang belum dilihat lebih dulu. Enter menampilkan
  statusnya: panah ke status berikutnya dan sebelumnya, Ctrl+panah ke orang berikutnya dan sebelumnya,
  Status suara dan video langsung diputar sendiri di add-on, tanpa program lain; Enter menghentikan atau
  memutarnya lagi, dan mendeskripsikan foto. Alt+Y menyukai, Alt+R membalas (di chat orangnya), Alt+D
  mengunduh foto, video, atau suaranya sebagai file, di folder yang Anda pilih. Melihat status menampilkan Anda di daftar yang melihat, seperti
  di WhatsApp.
- **Panggilan** menampilkan panggilan terbaru, termasuk yang tak terjawab. Enter menelepon balik.
- **Diarsipkan** menampilkan chat yang diarsipkan.

### Panggilan

Saat ada yang menelepon, add-on memutar nada dering dan menyebut siapa. **NVDA+Alt+A** mengangkat dan
**NVDA+Alt+H** menolak, dari mana saja; jendela panggilan muncul tanpa mengambil fokus. Saat panggilan,
Ctrl+M membisukan mikrofon dan NVDA+Alt+H mengakhirinya. Di chat, **Ctrl+Shift+C** menelepon orangnya.
Panggilan grup belum didukung. Di pengaturan NVDA Anda memilih mikrofon dan pengolahan suara panggilan.

### Notifikasi

Pesan baru dibacakan dengan suara. Di pengaturan NVDA Anda memilih suara untuk chat pribadi dan grup,
dan apakah isi pesan ikut dibacakan atau hanya pengirimnya. Di menu chat, **Notifikasi untuk chat ini**
mengatur aturan chat itu sendiri: selalu dibacakan (walaupun dibisukan) atau tidak pernah, suaranya
sendiri (salah satu suara add-on atau file WAV Anda), dan seberapa banyak yang diucapkan.

### Memilih beberapa pesan atau chat

Seperti mode Pilih di WhatsApp, di daftar chat dan di pesan sebuah chat:

- **Shift+Panah bawah** dan **Shift+Panah atas** memilih sambil bergerak; **Spasi** memilih atau batal
  memilih yang sekarang; **Ctrl+A** memilih semua. Bunyi tik pelan terdengar saat sampai di item terpilih.
- **Escape** membatalkan semua pilihan.
- Dengan pesan terpilih, **Ctrl+C** menyalinnya seperti WhatsApp (`[10:15, 8/11/2026] Nama: teks`, satu
  per baris), **Alt+F** meneruskannya, **Delete** menghapusnya, dan menu konteks juga bisa membintanginya.
- Dengan chat terpilih, menu konteks mengarsipkan, membisukan, menyematkan, menandai dibaca atau belum
  dibaca, atau menghapus semuanya, dan **Delete** menghapusnya setelah bertanya. Grup yang masih Anda
  ikuti tidak dihapus: keluar dari grupnya dulu.

Di daftar pesan, **Enter** memutar atau membuka pesan; Spasi sekarang untuk memilih.

### Di mana saja di jendela

| Tombol | Fungsinya |
|---|---|
| Alt+1 sampai Alt+4 | Menampilkan semua chat, chat belum dibaca, grup, atau favorit, seperti tab WhatsApp. |
| Alt+U | Di chat, ke pesan pertama yang belum dibaca, tempat WhatsApp menulis "5 pesan belum dibaca". Di daftar chat, memilih chat berikutnya yang punya pesan belum dibaca. |
| Ctrl+N | Memulai chat dengan nomor telepon, tanpa menyimpan kontak. |

Pesan yang mulai Anda tulis disimpan sebagai draf saat Anda meninggalkan chat, dan daftar chat menyebutnya.

### Percakapan

- Di bagian atas ada tombol berisi nama chat dan apa yang ditampilkan WhatsApp di bawahnya: online, kapan orangnya
  terakhir dilihat, atau "tidak ada info" kalau disembunyikan. Saat seseorang mulai mengetik atau
  merekam pesan suara, NVDA langsung mengucapkannya; di grup, NVDA menyebut siapa. Tekan **Alt+T**
  untuk mendengarnya kapan saja. Tekan tombol itu untuk info kontak: nomor telepon, info, dan grup
  yang sama; untuk grup, deskripsi, pembuatnya, dan pesertanya.
- Di sebelah nama, seperti di WhatsApp, ada **Panggilan suara** (Ctrl+Shift+C, tidak untuk grup) dan
  **Opsi lainnya**. Dari daftar pesan, Shift+Tab sampai ke Opsi lainnya, lalu Panggilan suara, lalu nama.
  Opsi lainnya berisi info kontak atau grup, cari di chat (Ctrl+F), pilih pesan, notifikasi untuk chat
  ini, arsipkan, bisukan, sematkan, tandai sudah atau belum dibaca, dan tutup chat.
- Daftar **Pesan** (Alt+P) dimulai dari pesan terbaru. Setiap pesan menyebut pengirimnya: "Anda" untuk
  pesan Anda, nama kontak untuk pesan orang lain. Balasan juga menyebut pesan yang dibalas, misalnya
  `Anas: Oke, mengutip Anda: "Jadi?"`. Membuka chat menandainya sudah dibaca, seperti di WhatsApp.
- Tekan **Panah Atas** di pesan pertama untuk memuat pesan yang lebih lama.
- Tekan **Enter** di pesan suara untuk mendengarkannya, dan sekali lagi untuk berhenti. **Ctrl+S**
  mengganti kecepatannya: 1x, 1.5x, atau 2x, seperti di WhatsApp.
- Tombol di pesan:

  | Tombol | Fungsinya |
  |---|---|
  | Enter | Memutar pesan suara atau suara video di add-on (Enter lagi menghentikan); membuka foto atau dokumen dengan program Windows-nya (Buka di menu melakukannya untuk video); memilih di polling. |
  | Alt+C | Menampilkan teks pesan saja, untuk dibaca per karakter, kata, atau baris. Pesan panjang selalu utuh. |
  | Ctrl+C | Menyalin teks pesan. |
  | Alt+Y | Memberi reaksi emoji. |
  | Alt+D | Mengunduh file pesan ke folder pilihan Anda. |
  | Delete | Menghapusnya, untuk Anda atau untuk semua orang. |
  | Alt+R | Membalasnya. |
  | Alt+F | Meneruskannya ke satu atau beberapa chat. |
  | Alt+L | Membuka tautan di pesan; bila ada beberapa, pilih salah satu. |
  | Alt+I | Info pesan untuk pesan Anda: siapa yang menerima, membaca, dan memutarnya, dan kapan. |
  | Alt+P | Mendeskripsikan foto dengan add-on AI Content Describer, bila terpasang. |
  | Ctrl+F | Mencari pesan di chat ini, termasuk yang lama. |

  Saat Anda menulis, lawan bicara melihat "mengetik…", seperti di WhatsApp. WhatsApp Web tidak punya
  transkrip pesan suara; fitur itu hanya ada di WhatsApp di ponsel.

- Untuk mengirim file, tekan **Alt+A** untuk memilihnya, atau salin di File Explorer lalu tekan **Ctrl+V**
  di kotak tulis. Foto dan video dikirim sebagai foto dan video, audio sebagai audio, selain itu (apk, exe,
  pdf, zip) sebagai dokumen. Yang Anda ketik menjadi keterangannya.
- Tekan tombol **Applications** atau **Shift+F10** di pesan untuk menu WhatsApp: balas, reaksi, salin,
  beri bintang, edit pesan Anda, hapus untuk Anda atau untuk semua orang.
- Tulis di **Ketik pesan** (Alt+E) lalu tekan **Enter** untuk mengirim. Selama kosong, jendela
  menawarkan voice note; begitu Anda menulis, yang muncul tombol Kirim.
- Untuk membalas satu pesan, pilih pesannya lalu tekan **Alt+R**. **Escape** membatalkan balasan.
- **Escape** kembali ke daftar chat. Di daftar chat, tombol Applications membuka menu chat:
  arsipkan, bisukan, sematkan, tandai sudah atau belum dibaca.

### Voice note

| Tombol | Fungsinya |
|---|---|
| Ctrl+R | Mulai merekam. Saat merekam: berhenti lalu memutarnya. Sesudahnya: memutarnya lagi. |
| Ctrl+Shift+R | Mengirim, dan menghentikan rekaman lebih dulu bila perlu. |
| Ctrl+Shift+D | Menjeda atau melanjutkan rekaman. |
| Ctrl+D | Membuangnya. |

Voice note direkam dari suara asli mikrofon, tanpa peredam gema, peredam bising, dan volume otomatis
dari browser, dalam stereo bila mikrofon punya dua kanal, dan pada 128 kilobit per detik. Perekam
bawaan WhatsApp memakai jauh lebih kecil. Semua ini bisa diubah di pengaturan NVDA.

## Pengaturan

Menu NVDA, Preferensi, Pengaturan, **WhatsApp Access**:

- **Bacakan pesan baru dari**: semua chat yang tidak dibisukan, hanya chat pribadi, hanya chat yang
  terbuka di jendela, atau tidak ada.
- **Mikrofon untuk voice note**: sambungkan dulu dengan NVDA+Shift+W untuk melihat semua mikrofon.
- **Bacakan pesan baru sebagai ganti notifikasi dan suara WhatsApp**, **Putar suara add-on**, dan
  **Pakai petunjuk** (tombol yang perlu ditekan, diucapkan setelah pesan seperti "Merekam").
- **Kecepatan putar pesan suara**.
- Lima volume, dalam persen: suara pesan baru dan nada dering; suara lainnya (terkirim, merekam,
  memilih); voice note dan video di chat; status; lawan bicara di panggilan. 0 membisukan jenis suara
  itu. Anda juga bisa mengubahnya tanpa membuka pengaturan: di jendela WhatsApp, jendela status, atau
  jendela panggilan, **F6** memilih volume mana (efek suara, notifikasi, voice note, status, panggilan),
  **F7** menurunkan dan **F8** menaikkannya 5 persen. Perubahannya langsung berlaku, juga untuk yang
  sedang diputar, dan disimpan.
- **Rekam voice note dalam stereo**, **Pakai suara asli mikrofon**, dan **Kualitas voice note**.
- **Periksa versi baru di GitHub sehari sekali** dan **Periksa pembaruan sekarang**.

## Pembaruan

WhatsApp Access diterbitkan di [halaman GitHub-nya](https://github.com/InfiArtt/whatsapp-access/releases),
bukan di NVDA Add-on Store. Sehari sekali, tak lama setelah NVDA menyala, add-on mencari versi baru di
sana. Kalau ada, add-on menampilkan apa yang baru dan menawarkan **Unduh dan pasang**; pemasang add-on
milik NVDA lalu memasangnya dan meminta NVDA dimulai ulang. **Nanti saja** menanyakan lagi keesokan
harinya. File-nya dicocokkan dengan checksum dari GitHub sebelum dipasang. Add-on tidak mengirim apa pun
tentang Anda: ia hanya menanyakan rilis terbaru ke GitHub.

## Privasi

Add-on hanya berbicara dengan browser di komputer Anda sendiri, dan memeriksa bahwa program yang
diajak bicara memang browser itu. Add-on tidak mengirim pesan Anda ke tempat lain.

WhatsApp tidak menyediakan akses seperti ini secara resmi. Add-on memakai WhatsApp Web seperti Anda
memakainya, dari akun dan browser Anda sendiri, tetapi ketentuan WhatsApp tidak mengizinkan
mengubah cara kerja aplikasinya. Gunakan dengan pertimbangan Anda sendiri.

## Lisensi

GNU General Public License, versi 2 atau lebih baru. Lihat COPYING.txt.
