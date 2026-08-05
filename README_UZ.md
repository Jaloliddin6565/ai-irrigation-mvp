# AI Irrigatsiya MVP

O'zbekiston fermerlari uchun sensorsiz sug'orish qarorini qo'llab-quvvatlash
tizimi.

Tizim Sentinel-2 sun'iy yo'ldosh kuzatuvlarini, tarixiy/bashorat qilingan
ob-havo ma'lumotlarini va fermer kiritgan dala/ekin/sug'orish ma'lumotlarini
shaffof, deterministik FAO uslubidagi kunlik suv balansi modeli orqali
birlashtirib, **tushuntirilgan, oraliq ko'rinishidagi sug'orish
tavsiyalarini** taqdim etadi.

## Bu tizim nima — va nima emas

Bu **qaror qabul qilishga yordam beruvchi taxmin**, o'lchov qurilmasi emas va
o'qitilgan AI modeli emas.

- Tizim ildiz zonasidagi tuproq namligini, tuproq pH darajasini, elektr
  o'tkazuvchanligini, organik moddani, ekin kasalligini yoki ekin hosildorligini
  **bevosita o'lchamaydi**.
- Suv tejashni yoki hosildorlik oshishini **kafolatlamaydi**.
- Asossiz aniqlik ko'rsatkichlarini ko'rsatmaydi.
- Har bir tavsiya **oraliq** ko'rinishida beriladi (masalan, 20–26 mm /
  200–260 m³/ga), taxmin sifatida belgilanadi va ishonch darajasi, ishonchni
  shakllantirgan omillar, foydalanilgan ma'lumot manbalari, ogohlantirishlar
  va bilingan cheklovlar bilan birga keladi.

> **Doimiy ko'rsatiladigan ogohlantirish:**
> "Ushbu tavsiya masofaviy ma'lumotlar, ob-havo modeli va fermer kiritgan
> ma'lumotlar asosidagi taxminiy qaror ko'magidir. Tizim tuproq namligini
> bevosita o'lchamaydi va agronom yoki suv xo'jaligi mutaxassisi xulosasini
> to'liq almashtirmaydi."

To'liq hisoblash metodologiyasi, o'lchov birliklari va versiyalar tarixi
`docs/methodology.md` faylida keltirilgan.

## Joriy holat

To'liq deterministik tahlil zanjiri amalga oshirilgan va sinovdan
o'tkazilgan (3-bosqich): ekin bosqichini aniqlash, aniq boshlang'ich
holatga ega kunlik suv balansi, ehtiyotkorlik bilan sun'iy yo'ldosh
tuzatishi va tushuntirilgan ishonch darajasiga ega oraliq ko'rinishidagi
sug'orish tavsiyasi — qarang `docs/methodology.md` va `docs/api.md`.
Jonli (live) Open-Meteo va CDSE Sentinel Hub provayderlari (4-bosqich)
amalga oshirilgan va asosan simulyatsiya qilingan HTTP orqali sinovdan
o'tkazilgan; haqiqiy hisob ma'lumotlari bilan ulanish bir marta, tor
doiradagi operator tekshiruvi sifatida tasdiqlangan (4.5-bosqich, qarang
`docs/security.md`). To'liq o'zbek tilidagi frontend ish jarayoni
(5-bosqich) — fermerni ro'yxatdan o'tkazish/tanlash, Leaflet xarita orqali
dala chegarasini chizish, sug'orishni qayd etish, tahlilni ishga tushirish,
tavsiya/ishonch/ma'lumot manbai ko'rsatish va grafiklar — ushbu backend
bilan `fixture` va `live` rejimlarining ikkalasi uchun ham amalga
oshirilgan. `DATA_MODE=fixture` standart va CI doim shu rejimda ishlaydi.
`main` shoxobchasi faqat xavfsiz asosni saqlaydi; barcha ilova ishlari
feature-shoxobchalarida olib boriladi va pull request orqali qo'shiladi.

## Xavfsizlik holati — boshqa mashinada ishga tushirishdan oldin o'qing

**Bu MVPda autentifikatsiya yo'q.** Fermerni ro'yxatdan o'tkazish faqat
ma'lumotlar bazasida yozuv yaratadi; frontend brauzerda faol fermer ID'sini
tanlaydi/eslab qoladi. Foydalanuvchi darajasidagi kirish nazorati yo'q — API
so'rovlari faqat ko'rsatilgan fermer/dala *mavjudligini* tekshiradi, so'rov
yuboruvchining unga haqli ekanligini emas. Aniq chegaralar uchun
`docs/security.md` fayliga qarang.

Bu qasddan qilingan qaror — mahalliy ishlab chiqish va nazorat qilinadigan
pilot loyihalar uchun, ammo **ommaviy/production muhitda ishlatish uchun
yaroqsiz**, toki haqiqiy autentifikatsiya va avtorizatsiya qatlami
qo'shilmaguncha. Backend identifikatsiya (`Farmer`), egalik (`farmer_id`
tashqi kalitlari) va avtorizatsiya (bitta bog'lovchi nuqta) tushunchalarini
ataylab alohida saqlaydi, shunda kelajakda bu qatlam qayta yozishga
muhtoj bo'lmaydi — ammo hozircha u mavjud emas.

## Ma'lumot rejimlari

- `DATA_MODE=fixture` — deterministik statik namuna ma'lumotlar, tashqi
  hisob ma'lumotlari talab qilinmaydi, interfeysda "DEMO / NAMUNAVIY
  MA'LUMOT" sifatida aniq belgilanadi. Bir xil kirish ma'lumotlari doim bir
  xil natija beradi.
- `DATA_MODE=live` — haqiqiy Sentinel Hub (Copernicus Data Space Ecosystem)
  va Open-Meteo so'rovlari, interfeysda "JONLI MA'LUMOT" sifatida aniq
  belgilanadi. Sentinel-2 sun'iy yo'ldosh kuzatuvlari va Open-Meteo
  ob-havo tarixi/bashorati — bular yagona jonli ma'lumot manbalari; hisob
  ma'lumotlari yo'q bo'lsa, tizim aniq xato qaytaradi, hech qachon jim
  ravishda fixture rejimiga o'tmaydi va hech qachon o'rnini bosuvchi soxta
  ma'lumot yaratmaydi.

## Mahalliy ishga tushirish

### Backend (fixture rejimida, standart)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"
copy ..\.env.example ..\.env    # fayl nomlarini ko'rish uchun; qiymat kiritish shart emas
alembic upgrade head            # SQLite sxemasini yaratadi
uvicorn app.main:app --reload
```

`.env.example` faqat o'zgaruvchi nomlarini ko'rsatadi — haqiqiy qiymatlar
yo'q. `DATA_MODE=fixture` bo'lsa, `.env` faylida hech narsa to'ldirmasdan
ham backend to'liq ishlaydi.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

So'ng brauzerda `http://localhost:5173` manzilini oching.

### Test va build buyruqlari

```bash
# Backend
cd backend
pytest                 # to'liq test to'plami
ruff check .           # kod uslubi
mypy app                # tip tekshiruvi

# Frontend
cd frontend
npm run lint            # ESLint
npm run test             # Vitest — faqat simulyatsiya qilingan backend
npm run build             # tsc --noEmit, so'ng production build
```

### Jonli (live) rejimda ishga tushirish

Jonli rejim haqiqiy CDSE (Copernicus Data Space Ecosystem) hisob
ma'lumotlarini talab qiladi:

1. Copernicus Data Space Ecosystem hisobingizdan CDSE OAuth mijoz
   (client ID + secret) oling.
2. Mahalliy, kuzatuvdan chiqarilgan (git-ignored) `.env` faylida:
   `DATA_MODE=live`, `CDSE_CLIENT_ID=...`, `CDSE_CLIENT_SECRET=...`
   qiymatlarini o'rnating. Haqiqiy qiymatlar hech qachon repozitoriyga
   kiritilmasligi kerak — `.env` doimo `.gitignore` da.
3. Backend jarayonini qayta ishga tushiring.
4. Frontend faqat backend bilan gaplashadi — brauzerdan hech qachon
   to'g'ridan-to'g'ri CDSE yoki Open-Meteo'ga so'rov yubormaydi.

## Dala ish jarayoni (fixture yoki jonli rejimda bir xil)

1. Fermer sifatida ro'yxatdan o'tish yoki telefon raqami bo'yicha mavjud
   profilni tanlash (`docs/security.md` — bu ishonchga asoslangan holat,
   haqiqiy autentifikatsiya emas).
2. Boshqaruv panelidan yangi dala qo'shish, xaritada chegarani chizish.
3. Ekin turi, ekish sanasi, tuproq va sug'orish usulini kiritish.
4. Ixtiyoriy: sug'orish voqeasini qayd etish.
5. Tahlilni ishga tushirish — tavsiya, ishonch darajasi, ma'lumot manbai
   paneli va sun'iy yo'ldosh/ob-havo/suv balansi grafiklarini ko'rish.
6. Tahlillar tarixini ko'rish — har bir tahlil alohida saqlanadi, hech
   qachon almashtirilmaydi.

## Bilingan cheklovlar

- Barcha agronomik qiymatlar (Kc egri chiziqlari, tuproq parametrlari,
  sug'orish samaradorligi) umumiy FAO-56 uslubidagi namunaviy qiymatlar —
  O'zbekiston sharoiti uchun kalibrlanmagan. Haqiqiy sug'orish qarorlari
  uchun ishlatishdan oldin **mahalliy dala sinovlari orqali tasdiqlanishi
  shart** — qarang `docs/methodology.md`.
- Tizim hech qachon tuproq namligini, pH darajasini yoki hosildorlikni
  bevosita o'lchamaydi va kafolatlangan natija va'da qilmaydi.
- Bu MVPda haqiqiy autentifikatsiya yo'q — faqat mahalliy ishlab chiqish
  va nazorat qilinadigan pilot loyihalar uchun mo'ljallangan.
- 6-bosqich yakuniy tekshiruvida aniqlangan qo'shimcha cheklovlar
  (`docs/methodology.md` "Known limitations", `docs/validation-plan.md`):
  ba'zi tavsiya sabablari hali inglizcha; katta dalalar uchun jonli
  Statistik API so'rovi ba'zan xato qaytarishi mumkin; Docker haligacha
  to'liq sinovdan o'tkazilmagan.

## Batafsil ma'lumot

Ingliz tilidagi to'liq qo'llanma uchun `README.md` fayliga qarang.
