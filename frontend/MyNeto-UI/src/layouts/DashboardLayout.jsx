import Sidebar from "../components/Sidebar"

function DashboardLayout({ children }) {
  return (
    <div
      style={{
        display: "flex",
        minHeight: "100vh",
        background: "#f4f7fb",
      }}
    >
      <Sidebar />

      <div
        style={{
          flex: 1,
          padding: "40px",
        }}
      >
        {children}
      </div>
    </div>
  )
}

export default DashboardLayout