export const AuthShell = ({ title, subtitle, children }) => (
  <div className="grid min-h-screen bg-[#F7F5F0] lg:grid-cols-[1fr_1.1fr]">
    <div className="relative hidden flex-col justify-between bg-[#171717] p-12 text-[#F7F5F0] lg:flex">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#8B1E2D] font-display text-xl font-bold">S</div>
        <span className="font-display text-xl font-bold">StaffBook</span>
      </div>
      <div>
        <div className="mb-4 h-px w-16 bg-[#C6A15B]" />
        <h2 className="max-w-md font-display text-4xl font-bold leading-tight">Attendance, salary and payments — one honest ledger.</h2>
        <p className="mt-4 max-w-md text-sm text-stone-400">Built for Indian shops, restaurants and medical stores. Record only exceptions, and StaffBook calculates earned salary, fines, advances and due dates for you.</p>
      </div>
      <div className="text-xs text-stone-500">Up to 100 active staff per business · In-app alerts only</div>
    </div>
    <div className="flex items-center justify-center px-5 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 flex items-center gap-2 lg:hidden">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#8B1E2D] font-display text-lg font-bold text-white">S</div>
          <span className="font-display text-lg font-bold">StaffBook</span>
        </div>
        <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-2 text-sm text-stone-600">{subtitle}</p>}
        <div className="mt-8">{children}</div>
      </div>
    </div>
  </div>
);

export const PhoneInput = ({ value, onChange, testid = "phone-input" }) => (
  <div className="flex">
    <span className="flex items-center rounded-l-lg border border-r-0 border-stone-300 bg-stone-100 px-3 text-sm font-semibold text-stone-600">+91</span>
    <input type="tel" className="inp rounded-l-none" inputMode="numeric" maxLength={10} placeholder="98765 43210" required value={value}
      onChange={(e) => onChange(e.target.value.replace(/\D/g, ""))} data-testid={testid} />
  </div>
);
