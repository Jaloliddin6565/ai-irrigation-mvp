import { describe, expect, it } from "vitest";

import { ApiError } from "./client";
import { mapFieldErrors } from "./fieldErrorMapping";

describe("mapFieldErrors", () => {
  it("flattens field_errors into a field-name -> message map", () => {
    const error = new ApiError(422, {
      code: "validation_error",
      message_uz: "Kiritilgan ma'lumotlarda xatolik bor.",
      field_errors: [
        { field: "wilting_point_override", code: "validation_error", message_uz: "So'lish nuqtasi 0 dan katta bo'lishi kerak." },
        { field: "name", code: "validation_error", message_uz: "Dala nomi to'ldirilishi shart." },
      ],
    });

    expect(mapFieldErrors(error)).toEqual({
      wilting_point_override: "So'lish nuqtasi 0 dan katta bo'lishi kerak.",
      name: "Dala nomi to'ldirilishi shart.",
    });
  });

  it("returns an empty object when the error has no field_errors", () => {
    const error = new ApiError(500, {
      code: "internal_error",
      message_uz: "Serverda kutilmagan xatolik yuz berdi.",
    });

    expect(mapFieldErrors(error)).toEqual({});
  });

  it("returns an empty object for a non-ApiError value", () => {
    expect(mapFieldErrors(null)).toEqual({});
    expect(mapFieldErrors(new Error("boom"))).toEqual({});
  });

  it("keeps only the first message when a field appears more than once", () => {
    const error = new ApiError(422, {
      code: "invalid_override_values",
      message_uz: "...",
      field_errors: [
        { field: "wilting_point_override", code: "invalid_override_values", message_uz: "first" },
        { field: "wilting_point_override", code: "invalid_override_values", message_uz: "second" },
      ],
    });

    expect(mapFieldErrors(error)).toEqual({ wilting_point_override: "first" });
  });
});
