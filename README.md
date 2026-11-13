# WebScout AI (personal)

Roz 3 trending websites dhoondta hai jin ki official iOS app App Store (iTunes Search) par nahi milti.
Main list mein sirf naam aur link. Verification detail alag button mein.

## Setup (free, computer band hone par bhi chalta hai)
1. GitHub par naya repo banayein aur ye saari files upload karein (.github folder samet).
2. Settings > Pages > Deploy from branch > main / root. Dashboard ka link mil jayega.
3. Actions tab > "WebScout daily scan" > Run workflow (pehla test).
4. Optional phone/desktop push: ntfy.sh par ek mushkil sa topic naam subscribe karein, phir
   repo Settings > Secrets and variables > Actions mein NTFY_TOPIC us naam se add karein.

## Sources
Hacker News (Show HN + front page, Algolia API), Lobsters hottest. iOS check: iTunes Search API.
Sab free hain, koi API key ya AI nahi.

## Limitations
- "App nahi mili" final proof nahi hai, isi liye har site par "needs verification" likha hai.
- Android (Play Store) ka free official API nahi, is liye check nahi hota.
- Roz 3 ki guarantee nahi: kam mili to utni hi dikhayega, fake nahi.
- Dashboard ki browser notification sirf tab aati hai jab page khula ho. Band computer par ntfy use karein.
