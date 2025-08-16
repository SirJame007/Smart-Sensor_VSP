#จัดการข้อมูลในรูปแบบตารางเรียกว่า DataFrame ย่อ pd 
import pandas as pd
#จัดการ ตัวเลข และการคำนวณทางคณิตศาสตร์ที่ซับซ้อน
import numpy as np

file_path = 'Somjai888_SoilMoisture_2025-07-21.csv' #เรียกชื่อไฟล์นี้มาอ่านข้อมูล
MIN_HOURS = 1.5 #ระยะเวลาขั้นต่ำที่จะใช้ในการวิเคราะห์
MIN_REPEAT_COUNT = 20 #ตรวจสอบค่าซ้ำกันเกินก่อนหา Slope
RISE_THRESHOLD = 3 # เกณฑ์การเพิ่มขึ้นของค่าความชื้น จุดถัดไป-จุดล่าสุด < RISE_THRESHOLD
WINDOW_SIZE = 50 # จำนวนจุดข้อมูลสำหรับคำนวณ Slope 
SLOPE_THRESHOLD = 0 # ค่าความชันที่ถือว่า "นิ่ง"

#WP คือจุดที่พืชเริ่มเหี่ยวเพราะดินขาดน้ำ FC คือความชื้นดินสูงสุดที่ยังไม่แฉะ
#อ้างอิงตัวเลขจาก คู่มือปฏิบัติงานวิเคราะห์สมบัติทางกายภาพของดิน ตารางที่ 7 การคำนวณความชื้นที่พืชนำไปใช้ได้จากค่า FC และ PWP หน้า 71
#Pv คือความชื้นที่พืชดูไปใช้ได้ % โดยปริมาตร หามาจาก Pv = Pw(%นน.ดินแห้ง)*As(ความถ่วงจำเพาะ)
#As ค่าความถ่วงจำเพาะปรากฏ ใช้ในการแปลงหน่วยความชื้นจากเปอร์เซ็นต์โดยน้ำหนักให้เป็นเปอร์เซ็นต์โดยปริมาตร


#ฟังก์ชั่นจัดการข้อมูลในคอลัม Value เปลี่ยนค่าอนันต์ให้หายไปแล้ว ลบแถวที่ไม่มีข้อมูลพร้อมจัดเรียงข้อมูล index ใหม่อีกรอบ
def clean_data(df):
    """ล้างค่า NaN และ inf ออกจาก DataFrame"""
    return df.replace([np.inf, -np.inf], np.nan).dropna(subset=['value']).reset_index(drop=True)
def find_valid_peak(df, min_hours, min_repeat_count, window_size, slope_threshold):
    if df.empty:
        return None, "ข้อมูลว่าง"
    df = clean_data(df)
    if df.empty:
        return None, "ข้อมูลว่างหลังจากลบ NaN/inf"
    
#นำข้อมูลใน value*10 เก็บที่ value_int
    df['value_int'] = (df['value'] * 10).astype(int)
#หา Index ของแถวที่มีค่าในคอลัมน์ 'value_int' สูงที่สุด(idxmax) Index นี้จะถูกเก็บไว้ในตัวแปร peak_idx
    peak_idx = df['value_int'].idxmax()
# ดึงค่าเวลา (timestamp) ณ จุดสูงสุดที่หาได้จาก peak_idx มาเก็บไว้ในตัวแปร peak_time
    peak_time = df.loc[peak_idx, 'unixtimestamp']
#ดึงค่าความชื้นสูงสุด ณ จุดเดียวกันมาเก็บไว้ในตัวแปร peak_value
    peak_value = df.loc[peak_idx, 'value_int']
#ตัดข้อมูลตั้งแต่แถวที่เป็น peak ไปจนถึงแถวสุดท้าย แล้ว ก็อปเป็น DataFrame ใหม่ พร้อม รีเซ็ต index ให้เริ่มจาก 0 เพื่อเอาไว้ใช้วิเคราะห์ต่อโดยไม่กระทบข้อมูลต้นฉบับ
#df.index.get_loc(peak_idx) หา ตำแหน่ง (location) ของ Index ที่ระบุ (peak_idx) เพื่อนำไปใช้กับ iloc เลือกข้อมูลตามตำแหน่งแถว
#df.iloc[...:] เลือกข้อมูลทั้งหมดตั้งแต่ตำแหน่งนั้นเป็นต้นไป
#copy(): คัดลอกข้อมูลออกมาเป็น DataFrame ใหม่ เพื่อให้การแก้ไข segment ไม่ส่งผลกระทบต่อ df เดิม.
    segment = df.iloc[df.index.get_loc(peak_idx):].copy().reset_index(drop=True)
# ตรวจว่าหลังจากตัดข้อมูลแล้วมีข้อมูลเหลืออยู่หรือไม่ ถ้าไม่มีข้อมูลหลังพีคก็ไม่ต้องวิเคราะห์ต่อ
    if segment.empty:
        return None, "Segment ว่างเปล่าหลัง peak"
#"เจอค่าสูงสุด → ตั้งเป็นค่าก่อนหน้า → เช็คค่าหลังจากนั้นว่ามีเพิ่มขึ้นผิดปกติหรือไม่
    prev_val = peak_value
    for i, row in segment.iloc[1:].iterrows():  #segment.iloc[1:]: หมายถึงการเลือกข้อมูลทั้งหมดใน DataFrame ที่ชื่อ segment ตั้งแต่แถวที่ 2 เป็นต้นไป(ตำแหน่ง 0 คือจุด Peak) iterrows(): เป็นฟังก์ชันของ Pandas ที่ใช้สำหรับวนลูปใน DataFrame
        diff = row['value_int'] - prev_val  #คำนวณหาผลต่าง ของค่าในแถวปัจจุบันกับค่าในแถวก่อนหน้า
        if diff >= RISE_THRESHOLD: #RISE_THRESHOLD = 3 # เกณฑ์การเพิ่มขึ้นของค่าความชื้น จุดถัดไป-จุดล่าสุด < RISE_THRESHOLD
            return None, "❌ มีการเพิ่มขึ้นหลัง peak" # ถ้าเงื่อนไขเป็นจริง (คือ ค่าเพิ่มขึ้นมากเกินไป) โค้ดจะหยุดทำงานทันทีและส่งค่า None
        prev_val = row['value_int'] #อัปเดตให้เป็นค่าของแถวปัจจุบัน เพื่อใช้ในการเปรียบเทียบกับแถวถัดไปในรอบต่อไป

    # หา final point โดยใช้ Moving Average Slope
    final_index = -1
    repeat_count = 0 #คือตัวแปรที่จะใช้ นับจำนวนครั้งที่ค่าซ้ำกัน ติดต่อกัน 0 คือยังไม่ได้นับ
    prev_val_for_repeat = segment['value_int'].iloc[0]
    for idx in range(1, len(segment)):
        if segment['value_int'].iloc[idx] == prev_val_for_repeat:
            repeat_count += 1
        else:
            repeat_count = 0
            prev_val_for_repeat = segment['value_int'].iloc[idx]
    # เมื่อเจอค่าซ้ำกันตามเกณฑ์แล้ว ให้เข้าลูปย่อยเพื่อวิเคราะห์ความชัน
        if repeat_count >= min_repeat_count:
            last_decreasing_index = -1
            for sub_idx in range(idx, len(segment)):
                if sub_idx >= window_size:
                    window_df = segment.loc[sub_idx - window_size:sub_idx]
                    x = window_df.index
                    y = window_df['value_int']
                    if len(x) > 1:
                        slope, _ = np.polyfit(x, y, 1)
                        if slope < slope_threshold:
                            last_decreasing_index = sub_idx
                        elif last_decreasing_index != -1:
                            final_index = last_decreasing_index
                            break
            if final_index != -1:
                break

    if final_index == -1:
        final_index = len(segment) - 1
    # 🔹 ถอยกลับไปหาตำแหน่งแรกที่ค่าซ้ำกับ final_index
    final_val = segment['value_int'].iloc[final_index]
    for back_idx in range(final_index):
        if segment['value_int'].iloc[back_idx] == final_val:
            final_index = back_idx
            break
    final_time = segment.loc[final_index, 'unixtimestamp']
    duration_hours = (final_time - peak_time).total_seconds() / 3600.0
    if duration_hours >= min_hours:
        return segment.loc[:final_index].copy(), "✅ ผ่านเกณฑ์เวลา"
    else:
        return None, "❌ ไม่ผ่านเกณฑ์เวลา"  # แก้ไข: เพิ่ม return statement ที่สมบูรณ์
# ===== โหลดข้อมูล =====
try:
    df = pd.read_csv(file_path)
    df['unixtimestamp'] = pd.to_datetime(df['unixtimestamp'], unit='s') + pd.Timedelta(hours=7)
    df.sort_values(by='unixtimestamp', inplace=True)
    df.reset_index(drop=True, inplace=True)
except FileNotFoundError:
    print(f"❌ ไม่พบไฟล์: {file_path}")
    exit()
except Exception as e:
    print(f"❌ เกิดข้อผิดพลาดในการอ่านไฟล์: {e}")
    exit()

valid_segment = None
while MIN_REPEAT_COUNT >= 5 and valid_segment is None:
    print(f"\n--- เริ่มการวิเคราะห์ด้วย MIN_REPEAT_COUNT = {MIN_REPEAT_COUNT} ---")
    # โหลดข้อมูลใหม่ในแต่ละรอบ
    try:
        df = pd.read_csv(file_path)
        df['unixtimestamp'] = pd.to_datetime(df['unixtimestamp'], unit='s') + pd.Timedelta(hours=7)
        df.sort_values(by='unixtimestamp', inplace=True)
        df.reset_index(drop=True, inplace=True)
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการอ่านไฟล์: {e}")
        break   
    data_search = clean_data(df)
    round_num = 1
    while not data_search.empty:
        segment, reason = find_valid_peak(data_search, MIN_HOURS, MIN_REPEAT_COUNT, WINDOW_SIZE, SLOPE_THRESHOLD) 
        if segment is not None:
            valid_segment = segment
            print(f"✅ พบช่วงที่ผ่านเกณฑ์ด้วย MIN_REPEAT_COUNT = {MIN_REPEAT_COUNT}")
            print(reason)
            break
        else:
            #print(f"❌ รอบที่ {round_num}: {reason}")  # แก้ไข: เอา comment ออก
            data_search = clean_data(data_search)
            if data_search.empty:
                break
            # ตรวจสอบว่ามีข้อมูลเหลืออยู่หรือไม่
            if len(data_search) == 0:
                break     
            peak_idx = (data_search['value'] * 10).astype(int).idxmax()
            peak_pos = data_search.index.get_loc(peak_idx)           
            # ตรวจสอบว่ายังมีข้อมูลหลัง peak หรือไม่
            if peak_pos + 1 >= len(data_search):
                break               
            data_search = data_search.iloc[peak_pos+1:].reset_index(drop=True)
            round_num += 1
    if valid_segment is None:
        #print(f"\n❌ ไม่พบช่วงที่ผ่านเกณฑ์ในรอบนี้ (MIN_REPEAT_COUNT = {MIN_REPEAT_COUNT})")  # แก้ไข: เอา comment ออก
        MIN_REPEAT_COUNT -= 5       
# ===== แสดงผลสุดท้าย =====
if valid_segment is not None:
    print("\n🎯 เจอช่วงที่ผ่านเกณฑ์แล้ว:")
    print(valid_segment)  
    # ✅ โค้ดที่เพิ่มเข้ามาสำหรับคำนวณและแสดงระยะเวลา
    peak_time = valid_segment.iloc[0]['unixtimestamp']
    final_time = valid_segment.iloc[-1]['unixtimestamp']   
    # คำนวณระยะเวลาทั้งหมดในหน่วยชั่วโมง
    evaporation_duration_hours = (final_time - peak_time).total_seconds() / 3600.0
    print(f"\nระยะเวลาระเหยของน้ำจากดิน: {evaporation_duration_hours:.2f} ต่อชั่วโมง")   
    peak_value = valid_segment.iloc[0]['value']
    final_value = valid_segment.iloc[-1]['value']
    if evaporation_duration_hours > 2:
        # คำนวณ SDR 
        SDR = (peak_value - final_value) / evaporation_duration_hours
        print(f"อัตราการระเหยของน้ำ (SDR): {SDR:.2f} % ต่อชั่วโมง")       
        if  SDR >= 2:
            soil_type = "ดินทราย"
        elif 0.5 <= SDR < 2:
            soil_type = "ดินร่วน"
        elif SDR < 0.5:
            soil_type = "ดินเหนียว"
        else: 
            soil_type = "ข้อมูลอาจไม่ถูกต้อง"
        print(f"คุณสมบัติดิน: {soil_type}")

#WP คือจุดที่พืชเริ่มเหี่ยวเพราะดินขาดน้ำ FC คือความชื้นดินสูงสุดที่ยังไม่แฉะ
#อ้างอิงตัวเลขจาก คู่มือปฏิบัติงานวิเคราะห์สมบัติทางกายภาพของดิน ตารางที่ 7 การคำนวณความชื้นที่พืชนำไปใช้ได้จากค่า FC และ PWP หน้า 71
#Pv คือความชื้นที่พืชดูไปใช้ได้ % โดยปริมาตร หามาจาก Pv = Pw(%นน.ดินแห้ง)*As(ความถ่วงจำเพาะ)
#As ค่าความถ่วงจำเพาะปรากฏ ใช้ในการแปลงหน่วยความชื้นจากเปอร์เซ็นต์โดยน้ำหนักให้เป็นเปอร์เซ็นต์โดยปริมาตร
        SOIL_PARAMS = {
    "ดินทราย": {"FC": 0.9, "PWP": 0.4, "Pv": 0.8},  
    "ดินร่วนปนทราย": {"FC": 0.14, "PWP": 0.6, "Pv": 0.12},
    "ดินร่วน": {"FC": 0.22, "PWP": 0.10, "Pv": 0.17},
    "ดินร่วนปนดินเหนียว": {"FC": 0.27, "PWP": 0.13, "Pv": 0.19},
    "ดินเหนียว": {"FC": 0.35, "PWP": 0.17, "Pv": 0.23},
}
        params = SOIL_PARAMS[soil_type]
        #หาอัตราการลดลงของความชื้นในดินต่อหน่วยเวลา วัดจากเซ็นเซอร์
        Dr = (SDR*evaporation_duration_hours) /100  #เทียบสัดส่วน
        print(f"Dr = {Dr:.2f} % ใน {evaporation_duration_hours:.2f} ชม. ")  

        #หาอัตราการสูญเสียน้ำเฉลี่ยของดินต่อชั่วโมง 
        MDR = Dr / evaporation_duration_hours 
        print(f"MDR : {MDR:.2f} ชม.")

        #Ks คือค่าสัมประสิทธิ์การขาดน้ำของพืช (1 = น้ำเพียงพอ, ต่ำกว่า 1 = เริ่มเครียดน้ำ)
        #TAW คือปริมาณน้ำในดินที่พืชสามารถใช้ได้ (TAW = FC − WP)
        #RAW ปริมาณน้ำที่พืชสามารถใช้ได้โดยไม่เกิดความเครียด (RAW = p × TAW, p คือส่วนที่พืชทนได้)
        TAW = params['FC'] - params['PWP']
        RAW = params['Pv'] * TAW   
        #Allen(Allen et. al., 1998
        #แสดงผลค่า Ks แจ้งเตือนต่างๆ
        Ks = (TAW - Dr) / (TAW - RAW)
        if 0.95 <= Ks <= 1:
            Ks_Alarm = "น้ำในดินเพียงพอ รดน้ำตามปกติได้เลย"
        elif 0.7 <= Ks < 0.95:
            Ks_Alarm =  "น้ำในดินเริ่มลด ควรเฝ้าระวังและเตรียมรดน้ำ"
        elif 0.4 <= Ks < 0.7:
            Ks_Alarm = "น้ำในดินต่ำ พืชเริ่มเครียดน้ำ ควรเพิ่มการรดน้ำ"
        elif Ks < 0.4:
            Ks_Alarm = "น้ำในดินต่ำมาก พืชขาดน้ำ รดน้ำทันที!"
        else:
            Ks_Alarm =  "น้ำในดินมากเกินความจุปกติ ควรลดเวลาการรดน้ำในรอบถัดไป"
        print(f"Ks = {Ks:.2f}, Ks_Alarm {Ks_Alarm}") 
else:
        soil_type = "ข้อมูลไม่เพียงพอสำหรับการวิเคราะห์"