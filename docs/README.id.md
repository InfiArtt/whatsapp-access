# WhatsApp Access

WhatsApp Access membawa WhatsApp Anda ke jendela sederhana yang dibuat untuk pembaca layar NVDA:
chat, voice note, status, panggilan, saluran, komunitas, dan pengaturan, semuanya dengan keyboard,
dengan ucapan yang jelas dan suara-suara kecil. WhatsApp Web berjalan tersembunyi di belakang, jadi
Anda tidak perlu menjelajahi halaman webnya sama sekali.

Ini cara lain melihat dan memakai WhatsApp Anda sendiri, bukan bot. Add-on hanya mengirim apa yang
Anda tulis, rekam, atau pilih, saat Anda memilih mengirimnya. Add-on tidak pernah menjawab atau
mengirim apa pun sendiri.

## Yang Anda perlukan

- Windows 10 atau 11, dan NVDA 2026.3 atau lebih baru.
- Salah satu browser ini terpasang, versi 120 atau lebih baru: Brave, Google Chrome, Chromium,
  Vivaldi, Opera, atau Microsoft Edge. Anda tidak perlu memakainya sendiri; add-on hanya meminjamnya.
- WhatsApp di ponsel Anda, untuk menautkan komputer ini sekali, seperti WhatsApp Web.

## Memasang

1. Buka [halaman Rilis](https://github.com/InfiArtt/whatsapp-access/releases/latest) dan unduh file
   yang berakhiran `.nvda-addon`.
2. Buka file itu, misalnya dengan menekan Enter padanya di File Explorer. NVDA menanyakan apakah
   add-on akan dipasang: pilih Ya.
3. Mulai ulang NVDA saat diminta.

Versi baru datang dengan cara yang sama, sendiri: lihat [Pembaruan](#pembaruan).

## Pertama kali

Tekan **NVDA+Shift+W**. Add-on menanyakan cara menjangkau WhatsApp:

- **Browser tersembunyi milik add-on** (disarankan). WhatsApp Web berjalan tanpa jendela, dengan
  profilnya sendiri, jadi browser Anda dan tab-tabnya tidak pernah disentuh. Ia bisa menyala bersama
  NVDA, jadi pesan baru dan panggilan sampai kapan saja. Ia memakai sekitar 1 GB memori, sebanyak WhatsApp Web di
  tab browser.
- **WhatsApp Web di browser Anda sendiri**, kalau Anda memang membukanya di sana. Lihat
  [Memakai browser Anda sendiri](#memakai-browser-anda-sendiri).

Lalu tautkan ke ponsel Anda, sekali:

1. Ketik nomor telepon Anda dengan kode negaranya, misalnya +62 812 3456 7890, lalu tekan Enter.
2. Add-on membacakan kode 8 karakter huruf demi huruf, dan menampilkannya dengan tombol Salin.
3. Di ponsel, buka WhatsApp, lalu Setelan, Perangkat tertaut, Tautkan perangkat, dan pilih
   **Tautkan dengan nomor telepon saja**. Ketik kodenya. Ponsel Anda mungkin juga menampilkan
   notifikasi yang memintanya.
4. Begitu ponsel menerimanya, add-on mengucapkan "Tertaut" dan membuka chat Anda.

Tautannya tetap. Menutup jendela, memulai ulang NVDA, atau memulai ulang Windows tidak membuat Anda
keluar. Anda menautkan lagi hanya kalau Anda memutus tautan komputer ini, mengeluarkannya di ponsel,
atau tidak memakai WhatsApp di ponsel sekitar 14 hari, seperti semua perangkat tertaut.

## Tombol yang paling sering dipakai

| Tombol | Di mana | Fungsinya |
|---|---|---|
| NVDA+Shift+W | Di mana saja | Membuka jendela WhatsApp. |
| Enter | Daftar chat | Membuka chat. |
| Alt+E | Di chat | Ke **Ketik pesan**; Enter mengirim. |
| Ctrl+R | Di chat | Merekam voice note; Ctrl+Shift+R mengirimnya. |
| Applications | Di pesan atau chat | Menunya: balas, reaksi, teruskan, hapus, dan lainnya. |
| Alt+T | Di chat | Mendengar apakah orangnya online atau kapan terakhir dilihat. |
| Ctrl+Tab | Di chat | Chat berikutnya di daftar; Ctrl+Shift+Tab yang sebelumnya. |
| Panah atas | Kotak pesan kosong | Mengedit pesan terakhir Anda, seperti di WhatsApp: Enter menyimpan, Escape membatalkan. |
| Ctrl+1 sampai Ctrl+8 | Jendela | Chat, Status, Panggilan, Diarsipkan, Berbintang, Saluran, Komunitas, Pengaturan. |
| NVDA+Alt+A | Di mana saja | Mengangkat panggilan, atau kembali ke jendela panggilan. |
| NVDA+Alt+H | Di mana saja | Menolak panggilan, atau mengakhirinya. |
| NVDA+Alt+M | Di mana saja | Mematikan atau menyalakan mikrofon saat panggilan. |
| Ctrl+/ | Jendela | Semua pintasan keyboard, per bagian. |
| Escape | Jendela | Kembali ke daftar chat, atau menutup jendela. WhatsApp tetap berjalan. |

Empat tombol yang bekerja di mana saja (NVDA+Shift+W, NVDA+Alt+A, NVDA+Alt+H, dan NVDA+Alt+M) bisa
diganti di dialog Input Gestures NVDA, kategori WhatsApp Access. Tombol di dalam jendela WhatsApp tidak
bisa diganti.

## Jendela

Jendela punya bagian, seperti bilah samping WhatsApp: **Chat** (Ctrl+1), **Status** (Ctrl+2),
**Panggilan** (Ctrl+3), **Diarsipkan** (Ctrl+4), **Berbintang** (Ctrl+5), **Saluran** (Ctrl+6),
**Komunitas** (Ctrl+7), dan **Pengaturan** (Ctrl+8). Ctrl+Tab dan Ctrl+Shift+Tab pindah ke bagian
berikutnya dan sebelumnya; di dalam chat, keduanya pindah ke chat berikutnya dan sebelumnya. Bagian ini bukan tab: tekan Tab melewati kontrol sebuah bagian untuk
sampai ke daftar **Bagian**, yang menyebut bagian mana yang sedang dibuka; pilih yang lain dengan
panah lalu tekan Enter.

Selama jendela ada di depan, Anda online bagi kontak Anda, seperti di WhatsApp Web. Saat Anda pindah
ke program lain atau menutup jendela, Anda offline lagi; WhatsApp tetap berjalan di belakang untuk
pesan baru dan panggilan.

### Chat

- Ketik di **Cari chat** (Alt+S) untuk mencari chat menurut nama. Alt+1 sampai Alt+4 menampilkan
  semua chat, chat belum dibaca, grup, atau favorit.
- Setiap chat di daftar (Alt+C) menyebut namanya, berapa pesan yang belum dibaca, apakah
  disematkan atau dibisukan, apakah pesannya sementara, apakah ada panggilan grup yang sedang
  berlangsung, dan pesan terakhir. Pesan yang mulai Anda tulis disimpan sebagai draf, dan daftar
  menyebutnya.
- **Enter** membuka chat. **Alt+U** memilih chat berikutnya yang punya pesan belum dibaca.
- Tombol Applications membuka menu chat: notifikasi untuk chat ini, arsipkan, bisukan, sematkan,
  tandai sudah atau belum dibaca. **Delete** menghapus chat setelah bertanya.
- **Ctrl+N** memulai chat dengan nomor telepon, tanpa menyimpan kontak. **Ctrl+Shift+N** membuat
  grup baru. **Ctrl+Shift+F** mencari pesan di semua chat.

### Sebuah chat

- Di bagian atas ada nama chat, dengan apa yang ditampilkan WhatsApp di bawahnya: online, terakhir
  dilihat, atau pesan sementara. Saat seseorang mulai mengetik atau merekam, NVDA mengucapkannya; di
  grup, NVDA menyebut siapa. Tekan namanya untuk info kontak atau grup.
- Di sebelah nama ada **Panggilan suara** (Ctrl+Shift+C) dan **Opsi lainnya**. Dari daftar pesan,
  Shift+Tab sampai ke Opsi lainnya, lalu Panggilan suara, lalu nama.
- Daftar **Pesan** (Alt+M) dimulai di tempat Anda berhenti membaca, di pesan pertama yang belum
  dibaca, atau di pesan terbaru. Setiap pesan menyebut pengirimnya ("Anda" untuk pesan Anda), isinya,
  pesan yang dibalasnya, reaksinya, waktunya, dan untuk pesan Anda, apakah sudah terkirim dan dibaca.
  Panah atas di pesan pertama memuat pesan yang lebih lama. Membuka chat menandainya sudah dibaca.
- Pemberitahuan seperti "Anas menambahkan Qisti" dibacakan dengan kata-kata WhatsApp. Foto dan video
  sekali lihat menyebut agar dibuka di ponsel, karena WhatsApp Web tidak bisa membukanya.

**Opsi lainnya** berisi apa yang ada di menu chat dan info chat WhatsApp:

- info kontak atau grup, cari di chat (Ctrl+F), pilih pesan;
- pesan yang disematkan, media, tautan, dan dokumen, dan di grup sebutan yang belum dibaca
  (Ctrl+Shift+M);
- **Kirim**: polling, kartu kontak, salah satu stiker Anda, atau acara di grup;
- di grup, memulai panggilan suara grup atau bergabung ke panggilan yang sedang berlangsung;
- notifikasi untuk chat ini, arsipkan, bisukan, sematkan, tandai sudah atau belum dibaca, favorit
  (kalau akun Anda punya), dan pesan sementara (mati, 24 jam, 7 hari, 90 hari);
- untuk admin grup, **Kelola grup**: nama, deskripsi, siapa yang boleh mengirim atau mengubah info,
  persetujuan anggota baru, tautan undangan (salin atau atur ulang), menambah anggota, dan menu tiap
  anggota untuk menjadikannya admin atau mengeluarkannya;
- blokir atau buka blokir, laporkan, bersihkan chat, keluar dari grup atau hapus chat, masing-masing
  ditanyakan dulu.

### Menulis dan mengirim

- Tulis di **Ketik pesan** (Alt+E) lalu tekan **Enter** untuk mengirim. Ketik @ di grup untuk
  menyebut seseorang: panah atas dan bawah memilih, Enter mengambilnya. Ketik : dan awal nama emoji
  dalam bahasa Inggris, seperti :grin atau :fire, untuk emoji: panah kiri dan kanan memilih, Enter
  mengambilnya.
- **Shift+Enter** membuat baris baru. **Ctrl+B**, **Ctrl+I**, dan **Ctrl+Shift+X** membuat teks yang
  dipilih tebal, miring, atau dicoret, seperti di WhatsApp; ditekan lagi, formatnya dilepas. Pesan
  dibacakan tanpa tanda formatnya; Alt+C menampilkannya seperti yang ditulis.
- Untuk membalas satu pesan, pilih pesannya lalu tekan **Alt+R**; Escape membatalkan balasan.
- Untuk mengirim file, tekan **Alt+A** untuk memilihnya, atau salin di File Explorer lalu tekan
  **Ctrl+V** di kotak pesan. Foto dan video dikirim sebagai foto dan video, audio sebagai audio,
  selain itu sebagai dokumen. Yang Anda ketik menjadi keterangannya.
- Selama Anda menulis, lawan bicara melihat "mengetik…", seperti di WhatsApp.
- **Menerjemahkan**, hanya saat Anda minta: **Ctrl+T** di sebuah pesan membacakannya dalam bahasa Anda
  (tekan dua kali untuk menampilkan terjemahannya dan membacanya baris demi baris). **Ctrl+T** di kotak
  pesan mengganti tulisan Anda dengan terjemahannya ke bahasa yang Anda pilih, misalnya Inggris, untuk
  dicek sebelum menekan Enter; Ctrl+T lagi mengembalikan kata-kata Anda. Pilih kedua bahasanya di
  pengaturan add-on. Terjemahan memakai Google Translate dan butuh internet.

### Voice note

| Tombol | Fungsinya |
|---|---|
| Ctrl+R | Mulai merekam. Saat merekam: berhenti dan memutarnya. Sesudahnya: memutarnya lagi. |
| Ctrl+Shift+R | Mengirimnya, menghentikan rekaman dulu kalau perlu. |
| Ctrl+Shift+D | Menjeda atau melanjutkan rekaman. |
| Ctrl+D | Membuangnya. |

Voice note direkam dari suara asli mikrofon Anda, tanpa peredam gema, peredam bising, dan pengatur
volume otomatis browser, dalam stereo kalau mikrofonnya dua kanal, dan pada 128 kilobit per detik,
jauh lebih jernih daripada perekam WhatsApp sendiri. Semuanya bisa diubah di pengaturan add-on.

### Tombol pada pesan

| Tombol | Fungsinya |
|---|---|
| Enter | Memutar pesan suara atau suara video (Enter lagi menghentikan); membuka foto atau dokumen; memilih di polling; detail acara. Pesan suara yang berurutan diputar beruntun, dan kursor ikut pindah. |
| Ctrl+S | Pesan suara 1x, 1,5x, atau 2x, seperti di WhatsApp. |
| Alt+C | Menampilkan teks pesan saja, untuk dibaca per huruf, kata, atau baris. |
| Ctrl+C | Menyalin teks pesan. |
| Alt+Y | Memberi reaksi emoji. |
| Alt+R | Membalasnya. |
| Alt+F | Meneruskannya ke satu chat atau lebih. |
| Alt+D | Menyimpan filenya ke folder pilihan Anda. |
| Alt+L | Membuka tautan di dalamnya. |
| Alt+I | Untuk pesan Anda: siapa yang menerima, membaca, dan memutarnya, dan kapan. |
| Alt+P | Mendeskripsikan foto dengan add-on AI Content Describer, bila terpasang. |
| Delete | Menghapusnya, untuk Anda atau untuk semua orang. |
| Applications | Menunya: juga bintangi, edit, sematkan 24 jam, 7 hari, atau 30 hari, balas secara pribadi di grup, lihat siapa yang bereaksi, dan jawab acara. |

### Memilih beberapa pesan atau chat

Seperti mode Pilih di WhatsApp, di daftar chat dan di pesan sebuah chat:

- **Shift+Panah bawah** dan **Shift+Panah atas** memilih sambil bergerak; **Spasi** memilih atau batal
  memilih satu; **Ctrl+A** memilih semua. Bunyi tik pelan terdengar saat sampai di item terpilih.
  **Escape** membatalkan pilihan.
- Dengan pesan terpilih, **Ctrl+C** menyalinnya seperti WhatsApp (`[10:15, 8/11/2026] Nama: teks`),
  **Alt+F** meneruskannya, **Delete** menghapusnya, dan tombol Applications juga bisa membintanginya.
- Dengan chat terpilih, tombol Applications mengarsipkan, membisukan, menyematkan, menandai sudah
  atau belum dibaca, atau menghapus semuanya. Grup yang masih Anda ikuti tidak dihapus: keluar dulu.

## Status

**Status** (Ctrl+2) menampilkan orang yang membuat status, yang belum dilihat lebih dulu. Enter
menampilkan statusnya:

- Panah ke status berikutnya dan sebelumnya, Ctrl+panah ke orang berikutnya dan sebelumnya.
- Status suara dan video diputar sendiri di dalam add-on. Enter menghentikan atau memutarnya lagi,
  dan mendeskripsikan foto.
- Alt+Y menyukai, Alt+R membalas di chat orangnya, Alt+D menyimpan foto, video, atau suaranya sebagai
  file.
- Melihat status menampilkan Anda di daftar yang melihat, seperti di WhatsApp.

Di bawah daftarnya: **Tulis status** (teks, dengan warna latar dan huruf), **Kirim foto atau video**,
dan **Status saya**, yang menyebut siapa saja yang melihat setiap status Anda dan bisa menghapusnya.

## Panggilan

Saat ada yang menelepon, add-on berdering sampai Anda mengangkat atau menolak, dan menyebut siapa, di mana pun Anda berada.
**NVDA+Alt+A** mengangkat dan **NVDA+Alt+H** menolak. Jendela panggilan muncul tanpa mengambil fokus.

Selama panggilan:

- **NVDA+Alt+M** mematikan atau menyalakan mikrofon dari program apa pun, dengan bunyi kecil untuk
  masing-masing. Di jendela panggilan atau jendela WhatsApp, Ctrl+M melakukan hal yang sama.
- **Escape** menyembunyikan jendela panggilan dan panggilan tetap berjalan, jadi Anda bisa terus chat.
  Jendela WhatsApp lalu menampilkan baris di atas dengan **Kembali ke panggilan** dan **Bisukan
  mikrofon**.
- NVDA+Alt+H mengakhiri panggilan. Kalau orang lain membisukan Anda, NVDA mengucapkannya.

Untuk menelepon: **Ctrl+Shift+C** di chat, atau Opsi lainnya, **Mulai panggilan suara grup**, di grup.
Grup yang sedang ada panggilan menyebut "panggilan sedang berlangsung" di daftar chat dan di bagian
atas **Panggilan** (Ctrl+3), tempat Enter bergabung. Kalau Anda diundang lagi, bergabung berarti
mengangkat panggilannya.

Di panggilan grup, jendela panggilan juga punya:

- daftar **Peserta**, yang ada di panggilan lebih dulu: siapa yang dibisukan, siapa yang mengangkat
  tangan, siapa yang belum bergabung; tombol Applications pada seseorang memintanya membisukan
  mikrofon;
- **Angkat tangan** (Ctrl+H) dan **Reaksi**, yang mengirim emoji ke semua peserta;
- **Ctrl+Shift+G**, di jendela panggilan atau jendela WhatsApp: siapa yang sedang berbicara.

NVDA menyebut siapa yang bergabung, keluar, mengangkat tangan, dan memberi reaksi, masing-masing
dengan bunyi kecilnya sendiri.

Panggilan diangkat dengan mikrofon dan tanpa kamera. Di pengaturan add-on Anda memilih mikrofon,
speaker, dan seberapa banyak pengolahan suara untuk panggilan. Untuk berganti saat panggilan, misalnya
dari headset ke speaker laptop, tekan **Mikrofon dan speaker** di jendela panggilan: panggilannya
langsung pindah. Voice note dan status diputar di speaker yang sama.

## Berbintang, Saluran, dan Komunitas

- **Berbintang** (Ctrl+5) menampilkan pesan berbintang dari semua chat. Enter membuka chatnya di
  pesan itu; tombol Applications menyalin atau menghapus bintang.
- **Saluran** (Ctrl+6) menampilkan saluran yang Anda ikuti. Enter membukanya: postingan dibaca
  seperti pesan, Alt+Y memberi reaksi, dan hanya admin saluran yang bisa memposting. **Cari saluran**
  mencari di direktori WhatsApp; menu saluran bisa berhenti mengikutinya.
- **Komunitas** (Ctrl+7) menampilkan komunitas Anda. Enter menampilkan grup-grupnya, pengumuman
  lebih dulu. Enter membuka grup yang Anda ikuti, atau meminta bergabung ke grup yang belum.

## Pengaturan WhatsApp Anda

**Pengaturan** (Ctrl+8) berisi pengaturan WhatsApp sendiri:

- **Profil**: nama, info, dan foto Anda.
- **Privasi**: terakhir dilihat, online, foto profil, info, siapa yang bisa menambahkan Anda ke grup,
  tanda dibaca, dan membisukan penelepon tak dikenal.
- **Kontak yang diblokir**: Enter membuka blokir.
- **Pengaturan add-on**: membuka pengaturan di bawah ini.

## Notifikasi, suara, dan volume

Pesan baru dibacakan dengan suara, sebagai ganti notifikasi WhatsApp sendiri. Di menu chat,
**Notifikasi untuk chat ini** mengatur aturan chat itu sendiri: selalu dibacakan (walaupun dibisukan)
atau tidak pernah, suaranya sendiri (salah satu suara add-on atau file WAV Anda), dan seberapa banyak
yang diucapkan.

Ada lima volume: suara pesan baru dan nada dering; suara add-on lainnya; voice note dan video di chat;
status; dan lawan bicara di panggilan. Di jendela WhatsApp, jendela status, atau jendela panggilan,
**F6** memilih volume mana, **F7** menurunkan dan **F8** menaikkannya 5 persen. Perubahannya langsung
berlaku dan disimpan.

## Pengaturan add-on

Menu NVDA, Preferences, Settings, **WhatsApp Access**:

- cara menjangkau WhatsApp (browser tersembunyi atau browser Anda), browser yang dipakai, dan menyala
  bersama NVDA;
- **Putuskan tautan komputer ini**: keluar dari WhatsApp di sini dan menghapus data browser
  tersembunyi;
- pesan baru mana yang dibacakan, dan apakah isinya ikut dibacakan;
- suara untuk chat pribadi dan untuk grup (berbeda sejak awal, supaya bisa dibedakan) dan nada dering:
  milik add-on, salah satu nada dering Windows, tidak ada, atau file WAV Anda sendiri. Bergerak di
  daftarnya memutar tiap suara, dan **Putar** memutar pilihan itu lagi atau menghentikannya;
- **Buka folder suara Anda sendiri**: file WAV yang Anda taruh di sana dengan nama salah satu suara
  add-on, misalnya sent.wav atau openChatMessage.wav (pesan di chat yang sedang dibuka), diputar
  menggantikannya. Folder itu berisi daftar namanya;
- mikrofon dan speaker, dan pengolahan suara di panggilan;
- voice note: stereo, suara asli mikrofon, kualitas;
- kecepatan putar, lima volume, suara add-on, dan petunjuk (tombol yang perlu ditekan berikutnya);
- pemeriksaan versi baru.

## Pembaruan

WhatsApp Access diterbitkan di
[halaman GitHub-nya](https://github.com/InfiArtt/whatsapp-access/releases), bukan di NVDA Add-on
Store. Sehari sekali, tak lama setelah NVDA menyala, add-on mencari versi baru di sana. Kalau ada,
add-on menampilkan apa yang baru dan menawarkan **Unduh dan pasang**; NVDA memasangnya dan meminta
dimulai ulang. **Nanti saja** menanyakan lagi keesokan harinya. Anda juga bisa memeriksa sekarang:
pengaturan add-on, **Periksa pembaruan sekarang**. File-nya dicocokkan dengan checksum dari GitHub
sebelum dipasang, dan add-on tidak mengirim apa pun tentang Anda.

## Memakai browser Anda sendiri

Kalau Anda memilih WhatsApp Web di browser Anda sendiri, bukan browser tersembunyi:

1. Buka web.whatsapp.com dan masuk, di Brave, Google Chrome, atau Microsoft Edge.
2. Nyalakan remote debugging di sana, sekali: buka tab baru dengan Ctrl+T, ketik
   `brave://inspect/#remote-debugging` (di Chrome `chrome://inspect/#remote-debugging`, di Edge
   `edge://inspect/#remote-debugging`), lalu centang "Allow remote debugging for this browser
   instance".
3. Setiap kali browser dinyalakan, NVDA+Shift+W yang pertama membawanya ke depan dengan pertanyaan
   "Allow remote debugging?". Fokusnya ada di Cancel: tekan Shift+Tab, lalu Enter, untuk
   mengizinkan.

Selama add-on tersambung, browser menampilkan baris yang menyebut ia sedang dikendalikan perangkat
lunak: itu add-on ini.

## Kalau ada masalah

- **"Still connecting to WhatsApp Web"**: WhatsApp sedang menyala, yang butuh sampai setengah menit
  setelah NVDA menyala. Coba lagi sebentar.
- **WhatsApp kehilangan koneksi**: NVDA mengucapkannya setelah beberapa detik dan lagi saat
  tersambung kembali. Pesan yang Anda kirim sementara itu terkirim begitu tersambung.
- **Ada pertanyaan terbuka tapi tidak terjangkau**: kembali ke jendela WhatsApp; add-on membawa Anda
  ke pertanyaan yang terbuka.
- **Anda diminta menautkan lagi**: WhatsApp mengeluarkan komputer ini dari perangkat tertaut. Tautkan
  lagi seperti pertama kali.

## Privasi

Add-on hanya berbicara dengan browser di komputer Anda sendiri, dan memeriksa bahwa program yang
diajak bicara memang browser itu. Add-on tidak mengirim pesan Anda ke mana pun, kecuali satu hal yang
Anda pilih setiap kali: Ctrl+T mengirim teks yang diterjemahkan ke Google Translate. Tidak ada yang
diterjemahkan dengan sendirinya.

WhatsApp tidak menyediakan akses seperti ini secara resmi. Add-on memakai WhatsApp Web seperti Anda
memakainya, dari akun Anda sendiri, tetapi ketentuan WhatsApp tidak mengizinkan mengubah cara kerja
aplikasinya. Gunakan dengan pertimbangan Anda sendiri.

## Lisensi

GNU General Public License, versi 2 atau lebih baru. Lihat COPYING.txt.
