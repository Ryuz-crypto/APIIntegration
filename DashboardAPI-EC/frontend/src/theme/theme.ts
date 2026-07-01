import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    mode: "dark",
    background: {
      default: "#101214",
      paper: "#171A1D"
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
    borderRadius: 8
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
          border: "1px solid rgba(255,255,255,0.08)"
        }
      }
    }
  }
});
