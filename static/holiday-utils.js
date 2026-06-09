/** HolidayUtils — 工作日/非工作日判定 */
(function() {
  const HolidayUtils = {
    holidays: new Set(),
    workdays: new Set(),
    async init() {
      // 中国法定节假日（2026年）
      const dates = [
        '2026-01-01', // 元旦
        '2026-02-17','2026-02-18','2026-02-19','2026-02-20','2026-02-21','2026-02-22','2026-02-23', // 春节
        '2026-04-05','2026-04-06', // 清明
        '2026-05-01','2026-05-02','2026-05-03','2026-05-04','2026-05-05', // 劳动节
        '2026-06-19','2026-06-20','2026-06-21', // 端午
        '2026-10-01','2026-10-02','2026-10-03','2026-10-04','2026-10-05','2026-10-06','2026-10-07','2026-10-08', // 中秋+国庆
      ];
      dates.forEach(d => this.holidays.add(d));
      const today = new Date().toISOString().slice(0, 10);
      if (this.holidays.has(today)) return true;
      const day = new Date().getDay();
      return day === 0 || day === 6; // 周六日
    }
  };
  window.HolidayUtils = HolidayUtils;
})();
