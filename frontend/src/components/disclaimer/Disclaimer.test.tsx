import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../i18n";
import { Disclaimer } from "./Disclaimer";

describe("Disclaimer", () => {
  it("renders the persistent Uzbek disclaimer text", () => {
    render(<Disclaimer />);

    expect(
      screen.getByText(/Tizim tuproq namligini bevosita o'lchamaydi/)
    ).toBeInTheDocument();
  });
});
