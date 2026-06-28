export default function TabBar({ tabs, activeTab, onChange }) {
  return (
    <div className="tab-bar">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`tab-item ${activeTab === tab.id ? "tab-item--active" : ""}`}
          onClick={() => onChange(tab.id)}
        >
          <span className="tab-icon">{tab.icon}</span>
          <span className="tab-label">{tab.label}</span>
        </button>
      ))}
      <div
        className="tab-indicator"
        style={{
          width: `${100 / tabs.length}%`,
          transform: `translateX(${tabs.findIndex((t) => t.id === activeTab) * 100}%)`,
        }}
      />
    </div>
  );
}
