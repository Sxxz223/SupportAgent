import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import AdminApp from "./admin/AdminApp";
import "./styles.css";

const Page = window.location.pathname === "/admin" ? AdminApp : App;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Page />
  </StrictMode>,
);
