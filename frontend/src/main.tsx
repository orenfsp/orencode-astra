import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { Header } from "./app/Header";
import { SessionProvider } from "./app/session";
import { AdminDashboardPage } from "./pages/admin/AdminDashboardPage";
import { AdminJudgesPage } from "./pages/admin/AdminJudgesPage";
import { AdminRanksPage } from "./pages/admin/AdminRanksPage";
import { AdminRatingPage } from "./pages/admin/AdminRatingPage";
import { AdminRegistryPage } from "./pages/admin/AdminRegistryPage";
import { AdminAuditPage } from "./pages/admin/AdminAuditPage";
import { AdminCompetitionPage } from "./pages/admin/AdminCompetitionPage";
import { AdminCompetitionsPage } from "./pages/admin/AdminCompetitionsPage";
import { AdminReferencePage } from "./pages/admin/AdminReferencePage";
import { CabinetPage } from "./pages/CabinetPage";
import { CalendarPage } from "./pages/CalendarPage";
import { CompetitionPage } from "./pages/CompetitionPage";
import { LoginPage } from "./pages/LoginPage";
import { MinistryPage } from "./pages/MinistryPage";
import { NavigatorPage } from "./pages/NavigatorPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { ProtocolPage } from "./pages/ProtocolPage";
import { VerifyPage } from "./pages/VerifyPage";
import { AnalyticsPage } from "./pages/admin/AnalyticsPage";
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
          <Route path="/competitions/:id/protocol" element={<ProtocolPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/start" element={<NavigatorPage />} />
          <Route path="/verify/:code" element={<VerifyPage />} />
          <Route path="/ministry" element={<MinistryPage />} />
          <Route path="/admin/analytics" element={<AnalyticsPage />} />
          <Route path="/cabinet" element={<CabinetPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/admin" element={<AdminDashboardPage />} />
          <Route path="/admin/ranks" element={<AdminRanksPage />} />
          <Route path="/admin/rating" element={<AdminRatingPage />} />
          <Route path="/admin/audit" element={<AdminAuditPage />} />
          <Route path="/admin/registry" element={<AdminRegistryPage />} />
          <Route path="/admin/judges" element={<AdminJudgesPage />} />
          <Route path="/admin/competitions" element={<AdminCompetitionsPage />} />
          <Route path="/admin/competitions/:id" element={<AdminCompetitionPage />} />
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
