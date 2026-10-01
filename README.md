# Mineral Water Recommendation System

โปรเจ็คตัวอย่างระดับปริญญาตรีสำหรับรายวิชา Graph Database / Advanced Database
พัฒนาด้วย **Streamlit + Neo4j Aura + Cypher** และออกแบบให้ deploy ผ่าน **GitHub → Streamlit Community Cloud** ได้โดยตรง

ระบบนี้ต่อยอดจาก notebook `MineralWater_RecommenderSystem_Neo4j` โดยใช้โครงสร้างกราฟเดียวกัน และเพิ่มหน้าจอสำหรับเพิ่ม / แก้ไข / ลบข้อมูลลูกค้า น้ำแร่ และความสัมพันธ์

## 1. แนวคิดของระบบ

ระบบใช้ Property Graph ดังนี้

```text
(Customer {customer_id, name})-[:SIMILAR_TO]-(Customer)
(Customer)-[:LIKES]->(Water {water_id, name, image})
```

`image` คือรูปน้ำแร่ที่ผู้ใช้อัปโหลด (ไม่บังคับ) เก็บเป็น byte array ใน node โดยระบบย่อรูปเป็น JPEG ไม่เกิน 480 px ก่อนบันทึก
น้ำแร่ที่ยังไม่ได้อัปโหลดรูปจะใช้รูปประจำแบรนด์ในโฟลเดอร์ `images/` โดยจับคู่จากชื่อ (เช่น `Nestle Pure Life` → `images/nestle-pure-life.jpg`)
ถ้าไม่มีรูปที่ชื่อตรงกัน จะแสดงรูปขวดที่ระบบวาดให้ แหล่งที่มาและสัญญาอนุญาตของรูปอยู่ใน `images/CREDITS.md`

ระบบแนะนำน้ำแร่ที่ **ลูกค้าที่มีรสนิยมคล้ายกันชอบ แต่เจ้าตัวยังไม่ได้ชอบ**

```text
score = จำนวนลูกค้าที่คล้ายกัน (SIMILAR_TO) ที่ชอบน้ำแร่นั้น
```

คำแนะนำอธิบายได้ (Explainable Recommendation) เพราะระบบแสดงชื่อลูกค้าที่คล้ายกันซึ่งชอบน้ำแร่นั้นประกอบด้วย

> `SIMILAR_TO` ถูกเก็บเพียงหนึ่ง relationship ต่อคู่ และ query แบบไม่สนทิศทาง `-[:SIMILAR_TO]-`
> จึงเป็นความสัมพันธ์สมมาตร: ถ้า A คล้าย B แล้ว B ก็คล้าย A ด้วย
> (ต่างจาก notebook ที่ query ตามทิศทาง `->` ผลคำแนะนำของลูกค้าบางคนจึงมากกว่าใน notebook)

## 2. โครงสร้างไฟล์

```text
MineralWater1/
├── app.py                  # Streamlit UI
├── neo4j_service.py        # Cypher + Neo4j Driver
├── requirements.txt
├── .gitignore
├── .streamlit/
│   ├── secrets.toml.example
│   └── secrets.toml        # สร้างเอง ไม่ถูก commit
├── images/                 # รูปประจำแบรนด์ + CREDITS.md
├── cypher/
│   ├── schema.cypher
│   └── recommendation.cypher
└── docs/
    └── PROJECT_GUIDE_TH.md
```

## 3. สร้าง Neo4j Aura

1. สร้าง AuraDB instance
2. เก็บค่า Connection URI, username และ password
3. URI ของ Aura โดยทั่วไปอยู่ในรูป `neo4j+s://...databases.neo4j.io`
4. อย่านำ password ไปใส่ในไฟล์ที่ commit ขึ้น GitHub

## 4. รันในเครื่อง

ต้องใช้ **Python 3.10 ขึ้นไป** (ข้อกำหนดของ `neo4j` 6.x และ `streamlit` รุ่นใน `requirements.txt`)

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

คัดลอกไฟล์ตัวอย่าง secrets (ถ้ายังไม่มี `.streamlit/secrets.toml`)

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

จากนั้นใส่ password จริงในไฟล์ `.streamlit/secrets.toml` แล้วรัน

```bash
streamlit run app.py
```

## 5. ครั้งแรกที่เปิดระบบ

1. เข้าเมนู **Admin / Setup**
2. กด **สร้าง Constraint + Demo Data** (ลูกค้า 10 คน น้ำแร่ 7 แบรนด์ ตาม notebook)
3. ระบบใช้ `MERGE` จึงกดซ้ำได้โดยไม่สร้าง node ซ้ำจาก key เดิม
4. จากนั้นทดลองเมนูต่าง ๆ

## 6. เมนูของระบบ

| เมนู | ทำอะไรได้ |
| --- | --- |
| Dashboard | จำนวน node / relationship, ความนิยมของน้ำแร่, โปรไฟล์ลูกค้า |
| Recommendations | น้ำแร่ที่แนะนำพร้อม score และเหตุผล |
| Customers | เพิ่ม / แก้ไขชื่อ / ลบลูกค้า |
| Waters | แกลเลอรีรูปน้ำแร่, เพิ่ม (พร้อมอัปโหลดรูป) / แก้ไขชื่อและรูป / ลบน้ำแร่ |
| Relationships | เพิ่ม / ลบ `LIKES` และ `SIMILAR_TO` ของลูกค้าแต่ละคน |
| Graph Explorer | กราฟรอบตัวลูกค้าที่เลือก |
| Admin / Setup | สร้าง constraint และข้อมูลตัวอย่าง |

การลบลูกค้าหรือน้ำแร่ใช้ `DETACH DELETE` จึงลบ relationship ที่เกี่ยวข้องไปด้วย

## 7. Deploy GitHub → Streamlit Community Cloud

1. สร้าง GitHub repository ใหม่
2. push ไฟล์ทั้งหมดขึ้น GitHub **ยกเว้น `.streamlit/secrets.toml`**
3. เข้า Streamlit Community Cloud แล้วเลือก Create app
4. เลือก repository, branch และ entrypoint = `app.py`
5. ใน Advanced settings → Secrets ใส่

```toml
[neo4j]
uri = "neo4j+s://YOUR_INSTANCE.databases.neo4j.io"
username = "YOUR_USERNAME"
password = "YOUR_PASSWORD"
database = "YOUR_DATABASE"
```

6. Deploy

## 8. ประเด็น Graph Database ที่นักศึกษาจะได้ฝึก

- Node, Label, Property
- Relationship และ Direction
- Constraint และ Unique Key
- `MATCH`, `MERGE`, `CREATE`, `SET`, `DELETE`, `DETACH DELETE`, `OPTIONAL MATCH`, `WITH`, `UNWIND`
- Graph traversal ผ่านลูกค้าที่คล้ายกัน → น้ำแร่
- Aggregation เช่น `count`, `collect`
- Recommendation จาก topology ของกราฟ
- Parameterized Cypher
- Python Driver และ connection pooling
- Streamlit UI
- Secrets และ cloud deployment

## 9. สิ่งที่ปรับปรุงจาก notebook ต้นแบบ

- ใช้ `MERGE` ใน seed data เพื่อรองรับการรันซ้ำ
- สร้าง `SIMILAR_TO` ครบทั้ง 12 คู่ในรายการ `similarities` (notebook รันทีละคู่ไว้เพียง 7 คู่แรก)
- มอง `SIMILAR_TO` เป็นความสัมพันธ์เชิงสมมาตรตอน query ด้วย `-[:SIMILAR_TO]-`
- เพิ่มหน้าจอ CRUD สำหรับ Customer, Water, `LIKES` และ `SIMILAR_TO`
- คำแนะนำแสดงชื่อลูกค้าที่คล้ายกันซึ่งเป็นที่มาของ score
- ใช้ parameterized Cypher แทนการต่อ string จาก input
- แยก database layer (`neo4j_service.py`) ออกจาก UI (`app.py`)
- ใช้ Streamlit Secrets แทนการพิมพ์ password ทุกครั้งหรือ hardcode Aura credential

## 10. แนวทางต่อยอดเป็นโครงงานนักศึกษา

สามารถเพิ่ม Login, rating บน `LIKES`, property ของน้ำแร่ (แหล่งน้ำ, ราคา, แร่ธาตุ), การคำนวณ `SIMILAR_TO` อัตโนมัติจากน้ำแร่ที่ชอบร่วมกัน (Jaccard), Graph Data Science similarity, PageRank, community detection และ evaluation metrics เช่น Precision@K/Recall@K ได้
