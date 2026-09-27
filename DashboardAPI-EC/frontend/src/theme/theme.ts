import { createTheme } from "@mui/material/styles";
import type { AppearanceSettings } from "../lib/api";

const fonts: Record<AppearanceSettings["font"], string> = {
  inter: "Inter, Arial, sans-serif",
  system: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  humanist: "Trebuchet MS, Verdana, sans-serif",
  technical: "Arial Narrow, Roboto Condensed, Arial, sans-serif",
  mono: "Consolas, 'Liberation Mono', monospace"
};

export const defaultAppearance: AppearanceSettings = {
  primary: "#2FBF9B",
  secondary: "#E6B655",
  header: "#0C0F11",
  background: "#0F1214",
  surface: "#171B1E",
  text: "#F3F5F4",
  icon: "network",
  font: "inter",
  panel_name: "DashboardAPI",
  welcome_message: "Inventario y capacidades obtenidas desde las APIs de EdgeConnect"
};

export const createDashboardTheme = (appearance: AppearanceSettings) => createTheme({
  palette: {
    mode: "dark",
    background: {
      default: appearance.background,
      paper: appearance.surface
    },
    primary: {
      main: appearance.primary
    },
    secondary: {
      main: appearance.secondary
    },
    error: {
      main: "#EF6A6A"
    },
    success: {
      main: "#53C57B"
    },
    text: {
      primary: appearance.text,
      secondary: `${appearance.text}B3`
    }
  },
  typography: {
    fontFamily: fonts[appearance.font],
    h1: { fontSize: "1.55rem", fontWeight: 700 },
    h2: { fontSize: "1.1rem", fontWeight: 700 },
    button: { textTransform: "none", fontWeight: 700 }
  },
  shape: {
    borderRadius: 12
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: { minHeight: 36 }
      }
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          border: "1px solid rgba(255,255,255,0.08)",
          boxShadow: "0 18px 50px rgba(0,0,0,.16)"
        }
      }
    },
    MuiDialog: {
      styleOverrides: {
        paper: { backgroundImage: "linear-gradient(145deg, rgba(47,191,155,.04), transparent 45%)" }
      }
    }
  }
});
