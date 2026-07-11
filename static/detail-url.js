// 标讯宝 — 详情页 URL 统一构造（唯一真相源）
function detailUrl(bid, keyword, region) {
  var base = '/detail/' + bid.id + '.html';
  var params = [];
  if (keyword && keyword.trim()) {
    params.push('q=' + encodeURIComponent(keyword.trim()));
  }
  if (region) {
    params.push('region=' + encodeURIComponent(region));
  }
  return params.length ? base + '?' + params.join('&') : base;
}
