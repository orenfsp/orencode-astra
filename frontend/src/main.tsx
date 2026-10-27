import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { Header } from "./app/Header";
import { SessionProvider } from "./app/session";
import { AdminCompetitionsPage } from "./pages/admin/AdminCompetitionsPage";
import { AdminReferencePage } from "./pages/admin/AdminReferencePage";
import { CabinetPage } from "./pages/CabinetPage";
import { CalendarPage } from "./pages/CalendarPage";
import { CompetitionPage } from "./pages/CompetitionPage";
import { LoginPage } from "./pages/LoginPage";
import { State } from "./shared/ui";
import "./styles.css";

function NotFound() {
  return <section className="section"><State code="404" title="Страница не найдена" text="Проверьте адрес или вернитесь в календарь." action={<Link className="button" to="/">К календарю</Link>} /></section>;
}

function App() {
  return (
    <div className="app-shell">
      <Header />
      <main className="page-width">
        <Routes>
          <Route path="/" element={<CalendarPage />} />
          <Route path="/competitions/:id" element={<CompetitionPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/cabinet" element={<CabinetPage />} />
          <Route path="/admin/competitions" element={<AdminCompetitionsPage />} />
          <Route path="/admin/reference" element={<AdminReferencePage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <footer className="site-footer page-width">
        <span>Федерация спортивного программирования · Оренбургская область</span>
        <span>Все персональные данные в демо-версии вымышлены</span>
      </footer>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <SessionProvider><App /></SessionProvider>
    </BrowserRouter>
  </StrictMode>,
);
