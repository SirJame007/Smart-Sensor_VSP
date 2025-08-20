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
#โค้ดที่เพิ่มเข้ามาสำหรับคำนวณและแสดงระยะเวลา
    peak_time = valid_segment.iloc[0]['unixtimestamp']
    final_time = valid_segment.iloc[-1]['unixtimestamp']   
#คำนวณระยะเวลาทั้งหมดในหน่วยชั่วโมง
    evaporation_duration_hours = (final_time - peak_time).total_seconds() / 3600.0
    print(f"\nวิเคราะห์ข้อมูลเพื่อหาชนิดดิน")
    print(f"ระยะเวลาระเหยของน้ำจากดิน: {evaporation_duration_hours:.2f} ต่อชั่วโมง")   
    peak_value = valid_segment.iloc[0]['value']
    final_value = valid_segment.iloc[-1]['value']
#ตรวจสอบ SDR มากกว่า 2 ชม.หรือไม่
    if evaporation_duration_hours > 2:
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
#Dr จะหาค่าความชื้นในดินที่มันลดลงใน ชม.ที่ผ่านเกณฑ์
        #Dr = (SDR*evaporation_duration_hours) /100  #เทียบสัดส่วน
        #print(f"Dr = {Dr:.2f} % ใน {evaporation_duration_hours:.2f} ชม. ")  
#หาอัตราการสูญเสียน้ำเฉลี่ยของดินต่อชั่วโมง 
        #print(f"MDR : {MDR:.2f} ชม.")


#ดึงข้อมูล FC PWP Pv เข้ามาคำนวณ
        import json
        with open('Plant_information.json', 'r', encoding='utf-8') as f:
            plant_data = json.load(f)
# ฟังก์ชันดึงข้อมูลดิน
        def get_soil_info(soil_type):
            if soil_type not in plant_data:
                return None
            return {k: v for d in plant_data[soil_type] for k, v in d.items()}
        soil_info = get_soil_info(soil_type)
        if soil_info:
            FC = soil_info["FC"]
            PWP = soil_info["PWP"]
            Pv = soil_info["Pv"]
            print(f"ข้อมูล{soil_type}: \nFC = {FC:.2f}\nPWP = {PWP:.2f}\nPv = {Pv:.2f}")
        else:
            print("ไม่พบข้อมูลดิน")
        def get_plant_info(plant_name, month):
            if plant_name not in plant_data:
                return None   
            for entry in plant_data[plant_name]:
                start, end = map(int, entry["age_months"].split('-'))
                if start <= month <= end:
                    return {"Zr": entry["Zr"], "Kc": entry["Kc"]}  
            return None
#กำหนดพืชที่ปลูก
        plant_name = "durian"
        print(f"Crop : {plant_name}")
        age_month = 6
        print(f"age : {age_month} month ")
        info = get_plant_info(plant_name, age_month)
        if info:
            Zr = info["Zr"]
            Kc = info["Kc"]
            print(f"Zr = {Zr} mm.\nKc = {Kc}")
           
#กำหนดค่าเซ็นเซอร์เรียลไทม์
        Realtime_Sensor = 0.17
       
#TAW (ปริมาณน้ำในดินที่พืชสามารถดูดใช้ได้ทั้งหมด)
#RAW (น้ำที่พืชดูดขึ้นมาได้ โดยไม่เกิดความเครียดน้ำ)
#Dr (น้ำที่หายไปจากราก)
        print(f"\nข้อมูลที่มาจากการคำนวณตามสมการ FAO-56")
        TAW = (FC - PWP)*Zr
        print(f"TAW : {TAW:.2f}") 
        RAW = Pv * TAW
        print(f"RAW : {RAW:.2f}")   
#กำหนดค่าเซ็นเซอร์เรียลไทม์
        Dr = (FC-Realtime_Sensor)* Zr
        print(f"Dr : {Dr:.2f}")

#ตรวจสอบ Rang Ks (0-1) 
#Ks (ค่าสัมประสิทธิ์การขาดน้ำของพืช)
        if Dr > RAW :
            Ks = (TAW - Dr) / (TAW - RAW)
            if Ks > 1:
                Ks = 1
            elif Ks < 0:
                Ks = 0
            print(f"Ks : {Ks:.2f}")    
#ตรวจสอบค่าเซ็นเซอร์ปัจจุบันมากกว่า FC (ความชื้นสูงสุดของดิน)
        else :
            RTS_FC = (Realtime_Sensor- FC)*100
            print(f"ค่าความชื้นปัจจุบัน มากกว่าค่าความชื้นสูงสุดในดินที่พืชจะดูดไปใช้ได้อยู่ {RTS_FC:.2f} % ")
            Ks = 1
#ฟังก์ชั่นการแสดงผลการแจ้งเตือนเกี่ยวกับค่า Ks
        if 0.95 <= Ks <= 1.0:
            Ks_Alarm = "น้ำในดินเพียงพอ พืชยังไม่เครียด ยังไม่ต้องรดน้ำเพิ่ม"
        elif 0.85 <= Ks < 0.95:
            Ks_Alarm = "เริ่มตึงตัวเล็กน้อย ปากใบเริ่มตอบสนอง เฝ้าระวัง"
        elif 0.70 <= Ks < 0.85:
            Ks_Alarm = "เครียดน้อย ปากใบปิดเด่นชัด เตรียมรดน้ำ"
        elif 0.50 <= Ks < 0.70:
            Ks_Alarm = "เครียดปานกลาง การสังเคราะห์แสงลดลง แนะนำรดน้ำ"
        elif 0.30 <= Ks < 0.50:
            Ks_Alarm = "เครียดสูง เสี่ยงความเสียหายชั่วคราวต่อระบบสังเคราะห์แสง ควรรดน้ำเร่งด่วน"
        elif 0.15 <= Ks < 0.30:
            Ks_Alarm = "เครียดรุนแรงใบเหี่ยวงอ การสังเคราะห์ต่ำมาก เสี่ยงเสียหายถาวร รดน้ำทันที!"
        elif Ks <0.20 <= Ks < 0.15:
            Ks_Alarm = "วิกฤต ใกล้/ถึงจุดเหี่ยวถาวร รดน้ำและบรรเทาความร้อนทันที!"
        elif Ks <0.20 <= Ks < 0.15:
            Ks_Alarm = "อันตราย ดินแห้งเกินไป พืชเข้าสู่จุดเหี่ยวถาวร"
        else:
            Ks_Alarm = "เกิดข้อผิดพลาดในการคำนวณ Ks"
        print(f"สถานะพืช : {Ks_Alarm}")
        #print(f"Ks = {Ks:.2f} สถานะพืช: {Ks_Alarm}")
else:
        soil_type = "ข้อมูลไม่เพียงพอสำหรับการวิเคราะห์"