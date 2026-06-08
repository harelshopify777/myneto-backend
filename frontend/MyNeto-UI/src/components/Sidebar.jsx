function Sidebar() {
  return (
    <div
      style={{
        width: "260px",
        background: "white",
        borderLeft: "1px solid #e5e7eb",
        padding: "24px",
        display: "flex",
        flexDirection: "column",
        gap: "20px",
      }}
    >
      {/* Logo */}
      <div>
        <h1
          style={{
            color: "#2563eb",
            fontSize: "28px",
            fontWeight: "bold",
          }}
        >
          MyNeto
        </h1>

        <p
          style={{
            color: "#6b7280",
            marginTop: "-10px",
          }}
        >
          מערכת פיננסית חכמה
        </p>
      </div>

      {/* Menu */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "12px",
          marginTop: "30px",
        }}
      >
        <button style={menuButton}>דאשבורד</button>

        <button style={menuButton}>הכנסות</button>

        <button style={menuButton}>הוצאות</button>

        <button style={menuButton}>תזרים</button>

        <button style={menuButton}>דוחות</button>

        <button style={menuButton}>עובדים</button>
      </div>
    </div>
  )
}

const menuButton = {
  background: "#f3f4f6",
  border: "none",
  borderRadius: "12px",
  padding: "14px",
  fontSize: "16px",
  cursor: "pointer",
  textAlign: "right",
}

export default Sidebar