function Dashboard() {
  return (
    <div>
      <h1
        style={{
          fontSize: "36px",
          marginBottom: "30px",
        }}
      >
        דאשבורד פיננסי
      </h1>

      <div
        style={{
          display: "flex",
          gap: "20px",
          flexWrap: "wrap",
        }}
      >
        <div style={cardStyle}>
          <h3>הכנסות</h3>
          <h2>₪120,000</h2>
        </div>

        <div style={cardStyle}>
          <h3>רווח נקי</h3>
          <h2>₪48,000</h2>
        </div>

        <div style={cardStyle}>
          <h3>מע״מ לתשלום</h3>
          <h2>₪12,400</h2>
        </div>
      </div>
    </div>
  )
}

const cardStyle = {
  background: "white",
  padding: "24px",
  borderRadius: "18px",
  width: "260px",
  boxShadow: "0 4px 12px rgba(0,0,0,0.05)",
}

export default Dashboard