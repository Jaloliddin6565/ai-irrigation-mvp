import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./en.json";
import ru from "./ru.json";
import uz from "./uz.json";

// Uzbek is the only fully-translated locale for this MVP. ru/en are
// intentionally partial — missing keys fall back to Uzbek via fallbackLng,
// demonstrating the translation architecture without a full ru/en rewrite.
void i18n.use(initReactI18next).init({
  resources: {
    uz: { translation: uz },
    ru: { translation: ru },
    en: { translation: en },
  },
  lng: "uz",
  fallbackLng: "uz",
  supportedLngs: ["uz", "ru", "en"],
  interpolation: { escapeValue: false },
});

export default i18n;
