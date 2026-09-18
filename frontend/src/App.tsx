import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { Overview } from "./pages/Overview";
import { Datasets } from "./pages/Datasets";
import { DatasetDetail } from "./pages/DatasetDetail";
import { Discovery } from "./pages/Discovery";
import { DiscoveryDetail } from "./pages/DiscoveryDetail";
import { Workshop } from "./pages/Workshop";
import { Runs } from "./pages/Runs";
import { RunDetail } from "./pages/RunDetail";
import { Evidence } from "./pages/Evidence";
import { Pipeline } from "./pages/Pipeline";
import { SystemStatus } from "./pages/SystemStatus";
import { Hermes } from "./pages/Hermes";
import { Migrations } from "./pages/Migrations";
import { NotFound } from "./pages/NotFound";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<Overview />} />
          <Route path="/datasets" element={<Datasets />} />
          <Route path="/datasets/:id" element={<DatasetDetail />} />
          <Route path="/discovery" element={<Discovery />} />
          <Route path="/discovery/:id" element={<DiscoveryDetail />} />
          <Route path="/workshops/:workshopId" element={<Workshop />} />
          <Route path="/runs" element={<Runs />} />
          <Route path="/runs/:id" element={<RunDetail />} />
          <Route path="/evidence" element={<Evidence />} />
          <Route path="/pipeline" element={<Pipeline />} />
          <Route path="/system" element={<SystemStatus />} />
          <Route path="/system/hermes" element={<Hermes />} />
          <Route path="/system/migrations" element={<Migrations />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
