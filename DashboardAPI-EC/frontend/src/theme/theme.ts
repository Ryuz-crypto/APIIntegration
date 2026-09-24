import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    mode: "dark",
    background: {
      default: "#0F1214",
      paper: "#171B1E"
    },
    primary: {
      main: "#2FBF9B"
    },
    secondary: {
      main: "#E6B655"
    },
    error: {
      main: "#EF6A6A"
    },
    success: {
      main: "#53C57B"
    },
    text: {
      primary: "#F3F5F4",
      secondary: "#A7B0AB"
    }
  },
  typography: {
    fontFamily: "Inter, Arial, sans-serif",
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
