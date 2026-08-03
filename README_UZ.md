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

To'liq hisoblash metodologiyasi va uning versiyalar tarixi suv balansi
dvigateli qo'shilgandan so'ng `docs/methodology.md` faylida bo'ladi.

## Joriy holat

Loyiha asos (foundation) bosqichida. Asosiy domen modellari, suv balansi
dvigateli va jonli (live) provayder integratsiyalari hali amalga
oshirilmagan. `main` shoxobchasi faqat mana shu xavfsiz asosni saqlaydi;
barcha ilova ishlari feature-shoxobchalarida olib boriladi va pull request
orqali qo'shiladi.

## Xavfsizlik holati — boshqa mashinada ishga tushirishdan oldin o'qing

**Bu MVPda autentifikatsiya yo'q.** Fermerni ro'yxatdan o'tkazish faqat
ma'lumotlar bazasida yozuv yaratadi; frontend brauzerda faol fermer ID'sini
tanlaydi/eslab qoladi. Kirish (login), parol yoki "bu dala shu fermerga
tegishlimi" degan ma'lumotlar bazasi darajasidagi tekshiruvdan tashqari
foydalanuvchi darajasidagi kirish nazorati yo'q.

Bu qasddan qilingan qaror — mahalliy ishlab chiqish va nazorat qilinadigan
pilot loyihalar uchun, ammo **ommaviy/production muhitda ishlatish uchun
yaroqsiz**, toki haqiqiy autentifikatsiya va avtorizatsiya qatlami
qo'shilmaguncha. Backend identifikatsiya (`Farmer`), egalik (`farmer_id`
tashqi kalitlari) va avtorizatsiya (bitta bog'lovchi nuqta) tushunchalarini
ataylab alohida saqlaydi, shunda kelajakda bu qatlam qayta yozishga
muhtoj bo'lmaydi — ammo hozircha u mavjud emas.

## Ma'lumot rejimlari

- `DATA_MODE=fixture` — deterministik statik namuna ma'lumotlar, tashqi
  hisob ma'lumotlari talab qilinmaydi, interfeysda "DEMO / FIXTURE DATA"
  sifatida aniq belgilanadi. Bir xil kirish ma'lumotlari doim bir xil
  natija beradi.
- `DATA_MODE=live` — haqiqiy Sentinel Hub (Copernicus Data Space Ecosystem)
  va Open-Meteo so'rovlari. Hisob ma'lumotlari yo'q bo'lsa, aniq xato
  qaytaradi; hech qachon jim ravishda fixture rejimiga o'tmaydi va hech
  qachon o'rnini bosuvchi soxta ma'lumot yaratmaydi.

## Batafsil ma'lumot

Ingliz tilidagi to'liq qo'llanma uchun `README.md` fayliga qarang.
