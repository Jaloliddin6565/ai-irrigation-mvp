import * as L from "leaflet";

// Leaflet-Geoman's built-in translation registry. Registering + activating
// "uz" here (module load, once) makes every draw/edit/drag/remove control
// tooltip and toolbar button title Uzbek instead of the library's English
// default — without forking or restyling the toolbar itself.
const UZ_GEOMAN_LANG = {
  tooltips: {
    placeMarker: "Xaritaga belgi qo'ying",
    firstVertex: "Chegaraning birinchi nuqtasini belgilang",
    continueLine: "Chegarani chizishni davom ettiring",
    finishLine: "Chiziqni tugatish uchun oxirgi nuqtani bosing",
    finishPoly: "Chegarani tugatish uchun boshlang'ich nuqtaga qayta bosing",
    finishRect: "To'rtburchakni tugatish uchun bosing",
    startCircle: "Doira chizishni boshlang",
    finishCircle: "Doirani tugatish uchun bosing",
    placeCircleMarker: "Doira belgisini qo'ying",
  },
  actions: {
    finish: "Tugatish",
    cancel: "Bekor qilish",
    removeLastVertex: "Oxirgi nuqtani o'chirish",
  },
  buttonTitles: {
    drawMarkerButton: "Belgi qo'yish",
    drawPolyButton: "Dala chegarasini chizish",
    drawLineButton: "Chiziq chizish",
    drawCircleButton: "Doira chizish",
    drawRectButton: "To'rtburchak chizish",
    editButton: "Chegarani tahrirlash (nuqtalarni surish)",
    dragButton: "Chegarani butunlay ko'chirish",
    cutButton: "Kesish",
    deleteButton: "Chegarani o'chirish",
    drawCircleMarkerButton: "Doira belgisi qo'yish",
    snappingButton: "Ilashtirish",
    pinningButton: "Mahkamlash",
    rotateButton: "Aylantirish",
  },
};

export function applyUzbekGeomanLang(): void {
  const pm = (L as unknown as { PM?: { setLang?: (lang: string, obj: unknown, fallback?: string) => void } })
    .PM;
  pm?.setLang?.("uz", UZ_GEOMAN_LANG, "en");
}
