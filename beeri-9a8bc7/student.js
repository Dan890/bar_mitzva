// Beeri Shlomo's content bundle (metadata). Content data is in data.js / timings.js / original_env.js,
// per aliyah: the first in this folder, the others in a2/, a3/ (index.html loads the chosen one, ?a=N).
window.STUDENT = {
  id: "beeri",                                 // storage namespace: beeri_* keys, IndexedDB "toraOr_beeri"
  name: "בארי שלמה",
  brand: "תורת בארי",
  subtitle: "הקריאה של בארי שלמה לבר מצווה",
  aliyot: [
    { id: 1, label: "ראשון",  dir: "",    ref: "שבת פרשת תצווה · עלייה ראשונה · שמות כ״ז כ׳ – כ״ח י״ב" },
    { id: 2, label: "שני",    dir: "a2/", ref: "שבת פרשת תצווה · עלייה שנייה · שמות כ״ח י״ג – ל׳" },
    { id: 3, label: "שלישי",  dir: "a3/", ref: "שבת פרשת תצווה · עלייה שלישית · שמות כ״ח ל״א – מ״ג" }
  ]
};

// pick the aliyah: ?a=N, else the last one opened, else the first
(function (S) {
  var m = /[?&]a=(\d+)/.exec(location.search), want = m ? +m[1] : 0, a = null, i;
  if (!want) { try { want = +localStorage.getItem(S.id + "_aliyah") || 0; } catch (e) {} }
  for (i = 0; i < S.aliyot.length; i++) if (S.aliyot[i].id === want) a = S.aliyot[i];
  a = a || S.aliyot[0];
  try { localStorage.setItem(S.id + "_aliyah", String(a.id)); } catch (e) {}
  S.aliyah = a;
  S.ref = a.ref;
  S.section = a.id === 1 ? null : "a" + a.id;   // the first aliyah keeps its original storage keys
  S.media = { full: a.dir + "media/full.oga" };
  S.files = ["data.js", "timings.js", "original_env.js", "refs_env.js"].map(function (f) { return a.dir + f; });
})(window.STUDENT);
