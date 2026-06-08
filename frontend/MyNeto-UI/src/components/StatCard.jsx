function StatCard({ title, value }) {
  return (
    <div className="bg-white rounded-3xl p-6 shadow-md border border-gray-100">
      
      <p className="text-gray-500 mb-3">
        {title}
      </p>

      <h2 className="text-3xl font-bold text-blue-700">
        {value}
      </h2>

    </div>
  );
}

export default StatCard;