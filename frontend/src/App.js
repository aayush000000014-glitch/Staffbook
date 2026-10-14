import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth, homeFor } from "@/context/AuthContext";
import { Loader } from "@/components/sb/Kit";
import AppLayout from "@/components/sb/AppLayout";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import Forgot from "@/pages/Forgot";
import Onboarding from "@/pages/Onboarding";
import Dashboard from "@/pages/Dashboard";
import Staff from "@/pages/Staff";
import StaffProfile from "@/pages/StaffProfile";
import Attendance from "@/pages/Attendance";
import Payments from "@/pages/Payments";
import Reports from "@/pages/Reports";
import Settings from "@/pages/Settings";
import Admin from "@/pages/Admin";
import MyAccount from "@/pages/MyAccount";

function Blocked() {
  const { signOut } = useAuth();
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#171717] p-6 text-[#F7F5F0]" data-testid="business-blocked">
      <div className="max-w-md text-center">
        <h1 className="text-2xl font-bold">Business deactivated</h1>
        <p className="mt-2 text-sm text-stone-400">This business account has been deactivated by StaffBook. Your data is safe. Please contact support to reactivate.</p>
        <button className="btn-gold mt-6" onClick={signOut} data-testid="blocked-logout-btn">Log out</button>
      </div>
    </div>
  );
}

function Guard({ role, children, allowUnonboarded }) {
  const { loading, user, business } = useAuth();
  const loc = useLocation();
  if (loading) return <Loader />;
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  if (user.role !== role) return <Navigate to={homeFor(user, business)} replace />;
  if (role !== "super_admin" && business?.status !== "active") return <Blocked />;
  if (role === "owner" && !allowUnonboarded && !business?.onboarded) return <Navigate to="/onboarding" replace />;
  return children;
}

function PublicOnly({ children }) {
  const { loading, user, business } = useAuth();
  if (loading) return <Loader />;
  return user ? <Navigate to={homeFor(user, business)} replace /> : children;
}

function Home() {
  const { loading, user, business } = useAuth();
  if (loading) return <Loader />;
  return <Navigate to={homeFor(user, business)} replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
          <Route path="/signup" element={<PublicOnly><Signup /></PublicOnly>} />
          <Route path="/forgot" element={<PublicOnly><Forgot /></PublicOnly>} />
          <Route path="/onboarding" element={<Guard role="owner" allowUnonboarded><Onboarding /></Guard>} />
          <Route element={<Guard role="owner"><AppLayout /></Guard>}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/staff" element={<Staff />} />
            <Route path="/staff/:id" element={<StaffProfile />} />
            <Route path="/attendance" element={<Attendance />} />
            <Route path="/payments" element={<Payments />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
          <Route path="/admin" element={<Guard role="super_admin"><Admin /></Guard>} />
          <Route path="/me" element={<Guard role="staff"><MyAccount /></Guard>} />
          <Route path="*" element={<Home />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-center" richColors />
    </AuthProvider>
  );
}
