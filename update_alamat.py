"""
Update alamat donatur berdasarkan data nama → alamat dari user.
Hanya update yang alamat-nya masih NULL.
"""
import sqlite3
import re

DB_PATH = 'data/keuangan.db'

# Data nama → alamat dari user (parsed from the provided list)
# Format: (nama_asli, alamat)
DATA = """
Ibu Suparmi	Gerdu, Giripurwo
Ibu Anggraini	Gerdu, Giripurwo
Ibu Lasmi	Gerdu, Giripurwo
Bapak Ibrahim	Gerdu, Giripurwo
Ibu Marni	Gerdu, Giripurwo
Bapak Wahyudi	Gerdu, Giripurwo
Wedangan Glintong	Gerdu, Giripurwo
Ibu   Endang	Gerdu, Giripurwo
Ibu Mursidah	Gerdu, Giripurwo
Bapak Guntoro	Gerdu, Giripurwo
Ibu Deni Nur	Gerdu, Giripurwo
Es Asem 	Gerdu, Giripurwo
Toni Phone	Gerdu, Giripurwo
Marno Mie Ayam 	Gerdu, Giripurwo
Bapak  Eko Anak Naga 	Giripurwo
Grand Phone	Giripurwo
Ibu Nuryati	Salak 2/4 Giripurwo
Ibu Sugeng  Win	Gudang Seng 1
Wr. Makan Jawa 	Gudang Seng 2
Wr Makan	Gudang Seng 3
Nyoto Roso Roti 	Kajen, Giripurwo
Bapak Eko Didik	Kajen, Giripurwo
 W.M Mbak Us	Kajen, Giripurwo
Donat Mini	Kajen, Giripurwo
Karibean	Kajen, Giripurwo
Bapak  Bokir	Kajen, Giripurwo
Bapak Rochmandani	Smkit Al Huda, Giriwono
Kaviar	Kedungringin, Giripurwo
W. Andalas Padang	Batas Kota, Giriwono
Ibu Very	Wonogiri
Ayam Goreng Mbah Wiji	Depan Smk Pancasila 1, Giritirto
Mbah Nardi Pecel 	Donoharjo
Sayur Lombok Ijo 	Donoharjo
Bapak Marjo	Sendang Sari, Giriwono
Bapak Suranto	Sendang Sari, Giriwono
Ibu Tari	Sendang Sari, Giriwono
Bapak Kasmin	Sendang Sari, Giriwono
Bapak Saimin	Sendang Sari, Giriwono
Ibu  Yati	Sendangsari , Giriwono
Bapak Nanang	Sendangsari, Giriwono
Bapak Maridi	Sendangsari, Giriwono
Ibu Endang	Sendangsari, Giriwono
Bapak Misdi	Sendangsari, Giriwono
Bapak Mukti Sayur	Pasar, Wonogiri
Bapak Arif Sumarwanto	Selogiri
Bapak Mul	Pasar, Wonogiri
Ibu  Tum 	Ngernak, Jatipurno
Ibu  Tanikem	Geneng, Purwosari
Ibu  Puji	Geneng, Purwosari
Ibu Sumiyem	Geneng, Purwosari
Ibu Ika Wiwit	Geneng, Purwosari
Ibu Sumikem	Geneng, Purwosari
Bapak  Kasimun	Geneng, Purwosari
Ibu Paryati	Geneng, Purwosari
Ibu Sriyatmi	Geneng, Purwosari
Bapak Erwin	Sonoharjo
Pondok Soto	Sonoharjo
Ibu  Parmi	Kedungsono, Bulusulur
W.M.   Tinah 	Kedungsono, Bulusulur
Ibu Suminem	Kedungsono, Bulusulur
Ibu  Ninik 	Kedungsono, Bulusulur
Ibu  Sam	Kedungsono, Bulusulur
Bapak Aris Diyanto	Kedungsono, Bulusulur
Ibu  Parni	Kedungsono, Bulusulur
Ibu Kristiani	Kedungsono, Bulusulur
Bakso Bende 	Manjung, Purwosari
W.M.   Nunik 	Manjung, Purwosari
Bengkel Cat P Gatot 	Pelem, Purwosari
Ibu Semi	Klemut, Bulusulur
Bapak Sulis	Klemut, Bulusulur
Ibu Lariyem	Klemut, Bulusulur
Bapak Supri	Klemut, Bulusulur
Bapak Madun	Klemut, Bulusulur
Bapak Tukiyo	Klemut, Bulusulur
Bapak Wanto	Klemut, Bulusulur
Ibu  Meisuri	Klemut, Bulusulur
Ibu  Tuginem	Klemut, Bulusulur
Ibu  Warti	Klemut, Bulusulur
Ibu Yanti	Klemut, Bulusulur
Ibu Yekti	Klemut, Bulusulur
Ibu Suryati	Klemut, Bulusulur
Ibu Sum	Kemenag, Wonogiri
Labiq Stoorr	Brumbung, Kaliancar
Ibu Lanny Nurhayati	Brumbung, Kaliancar
Hik Mulia Hati	Brumbung, Kaliancar
Ibu Mbah Mini 	Krisak, Singodutan
Pat Shop	Krisak, Singodutan
W.M.  Bu Maryanti	Krisak, Singodutan
Bapak Parji	Krisak, Singodutan
Asalma Still	Krisak, Singodutan
Wr. Hj. Mukinah	Krisak, Singodutan
Moro Seneng P Min	Krisak, Singodutan
Bakso Goyang Lidah	Singodutan
Warung Bu Yono  	Kantin Mulia Hati
Ibu  Dwi	Krisak, Singodutan
Bapak Bandung Sukat	Krisak, Singodutan
Ibu Endang 	Krisak, Singodutan
Sofa Sofi	Krisak, Singodutan
Ibu Surati	Raksasa, Kaliancar
Toko Reza	Raksasa, Kaliancar
Bapak Ari Widi	Tandon Pare
Mie Ayam Nugroho 	Nambangan, Selogiri
Mei Ayam Bakso Jempol	Nambangan, Selogiri
Ibu Maryam	Nambangan, Selogiri
Mie Ayam Pancasila 	Garon, Selogiri
Bakso Parabola	Selogiri
Ibu  Giyarni 	Ketonggo, Ngadirojo
Ibu  Mulyani 	Ketonggo , Ngadirojo
Ibu  Ratih 	Ketonggo , Ngadirojo
Ibu  Warsini 	Ketonggo , Ngadirojo
Ayam Geprek Wong Deso	Npc Ketonggo, Ngadirojo
Tika Londry	Npc Ketonggo, Ngadirojo
Toko Hoki Nesia	Ketonggo, Ngadirojo
Ibu  Wanti Nesia	Ketonggo, Ngadirojo
Toko Tiga Dara Nesia	Ketonggo, Ngadirojo
Hafiz Phone	NPC Ketonggo, Ngadirojo
Bakso Mie Ayam Wonogiri BMW	Ketonggo, Ngadirojo
Angkringan Pak Min 	Ngadirojo
Fc Rahma	Ngadirojo
Bapak Hafie	Straja Ngadirojo
R.M. Cipto	Ngadirojo
Mie Ayam Bakso Gapuro Tare	Tare Kerjo Lor Ngadirojo
Bapak Riyadi 	Barengan RT 3/8, Jaten Selogiri
Sita Com	Ngadirejo Wetan
Rm Alami Sayang	Ngadirojo
Bapak Widi	Ngadirojo
Toko Saroja	Tukluk Ngadirojo
Toko Pertanian Haya	Tukluk Kerjo Lor
Fafa Copy	Pondok Ngadirojo
Sbr 1	Ngadirojo
Sigit Buah	Ngadirojo
Ibu Lilis Sayur	Girimarto
Bapak Istamar 	Manggis Ngadirojo
Bapak Wiyanto	Manggis Ngadirojo
Ibu  Nur	Manggis 1/11 Ngadirojo
W.M.  Reva	Npc, Ngadirojo
Wr. Makan	Npc, Ngadirojo
Warung Makan Berkah	Npc, Ngadirojo
W.M.  Babe Win	Npc, Ngadirojo
Wr. Padang	Npc, Ngadirojo
Ibu Warmi	Banjardowo, Purworejo
Ibu Wakini	Banjardowo, Purworejo
Ibu Nanik	Banjardowo, Purworejo
Ibu Saminah	Banjardowo, Purworejo
Ibu Fani	Banjardowo, Purworejo
Rumah Cerdas	Kerdukepik, Giripurwo
Ibu Narmi	Banjardowo, Purworejo
Ibu Siti	Banjardowo, Purworejo
Ibu Eni Yakult	Banjardowo, Purworejo
Ibu Samini	Banjardowo, Purworejo
Ibu Waginah	Banjardowo, Purworejo
Toko Bu Rositah	Sumberejo, Purworejo
Ibu Suwarti	Jurug , Pokoh Kidul
Ibu Sunarni	Jurug , Pokoh Kidul
Ibu Winarni	Jurug, Pokoh Kidul
Ibu Purwanti	Jurug , Pokoh Kidul
Ibu Ririn	Jurug, Pokoh Kidul
Ibu Dwi Pratiani	Jurug, Pokoh Kidul
Bapak  Bm	Jurug, Pokoh Kidul
Bapak Warsito	Jurug , Pokoh Kidul
Bakso Margi Rahayu	Jurug, Pokoh Kidul
Ibu  Retno	Jurug, Pokoh Kidul
Ayuk Salon	Jurug, Pokoh Kidul
Ibu Dini	Jurug, Pokoh Kidul
Tb Tito	Lemah Ireng, Bulusulur
Bapak Agus Widada	Mundu, Purworejo
Bapak Yanto	Mundu, Purworejo
Ibu Asih	Mundu, Purworejo
Ibu  Suminem	Mundu, Purworejo
Ibu Sri Rejeki	Mundu, Purworejo
Ibu Sri Jamu	Mundu, Purworejo
Ibu Sikem	Mundu, Purworejo
Naufal Warnet	Mundu, Purworejo
Toko Miyanto	Mundu, Purworejo
Ibu Sularti	Mundu, Purworejo
Bapak Wahyudi	Mundu, Purworejo
Ibu Sutiyem	Mundu, Purworejo
Ibu Purwanti	Mundu, Purworejo
Ibu  Maryanti	Ngerco, Ngadirojo Lor
Ibu Anis	Ngerco, Ngadirojo Lor
Ibu Nanik	Ngerco, Ngadirojo Lor
Ibu Ana Irianti	Ngerco, Ngadirojo Lor
Ibu Ayuk Salon	Norogo, Pokoh Kidul
Rm Bundar	Norogo, Pokoh Kidul
Bapak Dani	Ngrangkok, Purworejo
Ibu Listyorini	Ngrangkok, Purworejo
Bapak Aji Semin	Semin Wetan, Purworejo
Al Masah Hijab ( Feri )	Semin, Purworejo
Bapak Tarto	Semin, Purworejo
Bapak Afif Atullah	Semin Wetan, Purworejo
Toko Kembar	Sumberejo, Purworejo
Ibu Winarti	Sumberejo, Purworejo
Ibu Win	Sumberejo, Purworejo
Ibu Kasinah	Sumberejo, Purworejo
Ibu Siti	Sumberejo, Purworejo
Ibu Ndari Rahayu	Sumberejo, Purworejo
Ibu Galuh S R	Sumbersari
Parfum Saa	Pokoh, Wonoboyo
Ibu  Zulaikha	Pokoh, Wonoboyo
Al Madina	Pokoh Wonoboyo
Tama Parfum 	Pokoh, Wonoboyo
Setyo Rahayu Motor	Pokoh, Wonoboyo
Sugiyarto Cukur 	Pokoh, Wonoboyo
Ud. Masa 	Pokoh, Wonoboyo
Gording Aulia	Pokoh, Wonoboyo
Ibu Sunarni Soto Kwali 	Pokoh, Wonoboyo
Ibu Nur Azizah	Pokoh , Wonoboyo
Mie Ayam Bakso Econe	Pokoh, Wonoboyo
Mie Ayam Sido Maju	Wonoboyo
BaksoMan	Banaran, Wonoboyo
Sunarni Soto Kwali 	Banaran, Wonoboyo
Mie Ayam Tarni	Banaran, Wonoboyo
Bapak Bahtiar Arif	Jatirejo, Wonoboyo
Laundri 24 Jam 	Bantarangin, Bulusulur
Ibu Lilis Nureni	Bantarangin, Bulusulur
W.M.  Rizki 999 	Jatibedug, Bulusulur
Giri Tani 	Bulusari, Bulusulur
Rumah Siomay 	Bulusari, Bulusulur
Toko Lestari	Bulusari, Bulusulur
Dwi Mulya	Bulusari, Bulusulur
Kantin Dinas Pendidikan	Bulusari, Bulusulur
Bapak Manto ( Laundri) 	Bulusari, Bulusulur
Mie Ayam Bakso Wajan Heri	Bulusulur, Bulusulur
Bakso Derogab	Bulusulur, Bulusulur
Saa Parfum 02	Bulusulur, Bulusulur
Ibu Mak Roh 	Salak, Giripurwo
Ibu  Fika 	Salak, Giripurwo
Bakso Gun	Salak, Giripurwo
Mie Ayam Sor Sawo 	Salak, Giripurwo
Geprek Mangka Happy	Salak, Giripurwo
Jambe Digital	Salak, Giripurwo
Tm. Mart	Salak, Giripurwo
Sate Jaman	Salak, Giripurwo
Ibu  Nur	Salak, Giripurwo
Bapak Gino Z  1 & 2	Sanggrahan, Giripurwo
Yanti Toko	Sanggrahan, Giripurwo
Sasino Cafe	Sanggrahan, Giripurwo
W. Asem Gedhe	Sanggrahan, Giripurwo
Petshop 3 Bersaudara	Sanggrahan, Giripurwo
Raya Printing	Sanggrahan, Giripurwo
Anisah Com	Sanggrahan, Giripurwo
Kedai Gemes	Ngadirojo Kidul , Ngadirojo
Kedai Pramuka	Wonogiri
Bapak Riyadi	Semin Wetan, Purworejo
Bakso Tenis 	Alas Kethu, Giriwono
Warung Dandang 	Alas Kethu, Giriwono
Ibu Deny Nurhayati	Gandul 3/1 Giriwono
Ibu  Krebo Mariyem	Gandul , Giriwono
Bapak Sartono	Gandul, Giriwono
Ibu Asih Wiyarni	Perum Roland, Giriwono
Ibu  Jum	Timang, Giriwono
Bapak Katimin	Pokoh , Wonoboyo
Ibu  Suryani 	Timang, Giriwono
Mie Ayam Bakso timur masjid	Timang, Giriwono
Warung Manyol 	Timang, Giriwono
Wr.  Yanti 	Timang, Giriwono
Firs Cell 	Wonokarto, Wonokarto
Bapak Pardi Pigura 	Wonokarto, Wonokarto
Wakino Wm  Sederhana	Wonokarto, Wonokarto
Ibu Meidela	Wonokarto, Wonokarto
Ibu Purwanti	Wonokarto, Wonokarto
Fc Dkk	Wonokarto, Wonokarto
Rolan 	Wonokarto, Wonokarto
Warung Tenis	Wonokarto, Wonokarto
Ayam Geprek Barokah	Wonokarto, Wonokarto
Toserba Baru	Wonogiri
Ibu Luluk Puji M	Wonogiri
Ibu  Ning Snack	Wonogiri
Mie Ayam Es Asem	Wonogiri
Toko Kelontong	Wuryantoro
Toko Plastik	Wuryantoro
Ibu Mei Ceker	Wuryantoro
Muji Servis Komputer	Wuryantoro
Bintang Jaya	Wuryantoro
Lilas Hijab	Wuryantoro
Hik Cengkal	Wuryantoro
Wr Seblak Candra	Wuryantoro
Ibu  Nanik	Wuryantoro
Bapak Wawan Arifianto, St	Kerdukepik, Giripurwo
Ibu Siti Latifah	Sumberejo 3/3 Purworejo Wng
Ibu Sri Martini	Salak 2/4 Giripurwo Wonogiri
Bapak Hamba Alloh	Wonogiri
Bapak Tulus Marsudi	Pokoh Wonoboyo
Bapak Winarno Dwinanto	Jogja
Ibu Rodia	Pkpu
Ibu Fitri Mufidah	Pkpu
Infaq Ambulan	Wonogiri
Ibu Ummi Naufal	Ngadirojo
Bapak Toni Budi Cahyono	Sambirejo 1/13 Wonokerto
Bapak Topo	Bauresan
Ibu Yuni Sate	Selogiri
Ibu Suwarmi	Barengan, Jaten
Bapak Warsiadi	Kedungsono 2/6 Bulusulur
Ibu Tri Retno Ambarwati	Wonokarto, Wonokarto
Al Maidah	Krisak, Singodutan
Pondok Dahar Segle	Singodutan
Bapak Hamba Alloh	Sanggrahan, Giripurwo
Bapak Hamba Alloh	Krisak, Singodutan
Ibu Wahyuni Hidayati	Giri Asri, Kaliancar
Ibu Retno Hastuti	Pokoh Wonoboyo
Ibu Sulasmi	Mojopuro, Wuryantoro
Ibu Waryanti	Pulorejo Nambangan Selogiri
Ibu Tri Retno Ambarwati	Wonokarto, Wonokarto
Ibu Dwi Hartati	Keblokan Sendangijo
Ibu Sri Hartuti	Karangasem Selogiri
Ibu Hartini	Karangasem Selogiri
Bapak Suratman	Krisak Wetan Singodutan Selogiri
Foto Copy Map Com	Manjung Pojok
Bapak Hamba Alloh	Kedungsono 2/6 Bulusulur
Bapak Samsudin	Mirahan 2/2 Tanjungsari
Bapak Ilham Akhyar M	Brajan 1/5 Kaliancar
Ibu Novi Al Jannah	Pokoh 4/1, Wonoboyo
Bapak Agus Tri Bintoro	Banaran 1/11 Wonoboyo
Bapak Suratman 	Pelem 1/14 Purwosari
Bapak Muhammad Rafiqih	Salak 2/4 Giripurwo Wonogiri
Ibu Resya Ardani	Sumberejo 3/3 Purworejo Wng
Bapak Suyatno	Jatibedug 4/7 Purworejo
Bapak Sriyono	Sdit Alhuda
Ibu Anes Nindya Awti	Salak I No 17 Rt 1/4, Giripurwo
Bapak Dewaky Hendry A	Kerdukepik, Giripurwo
Ibu Yuni Nanda Saputri	Sambirejo 1/13 Wonokerto
Ibu Dwi Palupi	Tukluk 2/5 Tanjungsari Tirtomoyo
Bapak Heru Wijanarko Agung P	Semin Wetan 2/2, Purworejo
Bapak Samuji	Krisak Wetan 2/4 Singodutan
Ibu Amanah Noer Azizah M	Jatirejo 3/9 Wonoboyo
Ibu Sarmi	Bulusari 2/4 Bulusulur
Ibu Sri Habsari Kristiyanti	Salak 1/4 Giripurwo
Ibu Reni Romana	Gerdu 3/7 Giripurwo
Bapak Agus Saputro	Jl.Kelengkeng Kerdukepik
Bapak Wahyu Wibowo	Kerdukepik 4/1, Giripurwo
Ibu Rian Nurahma A	Geneng 1/12 Purwosari
Bapak Agus Rahmat	Sobo 1/6 Geneng
Bapak Budiyanto	Sedeng 1/10 Hargosari Tirtomoyo
Bapak Sunarto	Manjung Kulon 3/4, Purwosari
Bapak Lasmanto	Jatibedug 4/7 Purworejo
Bapak Suparno	Kajen 1/10, Giripurwo
Bapak Widiyanto	Karang Tengah 2/2 Singodutan
Ibu Fitri Mufida Qq Wisnu	Ceperan 2/7 Jendi
Ibu Fitri Mufidah	Ceperan 2/7 Jendi
Bapak Tri Efendi	Pudak 1/2 Beji Nguntoronadi
Bapak Larno Qq Sdit Ulin Nuha	Ngaglik 1/2 Pulutan
Ibu Aprilia Prasanti	Lingk Kajen 1/11 Giripurwo
Bapak Paulus Supriyanto	Ling. Ngersik 2/1 Beji
Bapak Dandi Saputra	Tukluk 3/15 Kerjo Lor
Bapak Herry Prihanto	Bulusari 3/9 Bulusulur
Ibu Aru Kusuma M	Brumbung 4/7 Kaliancar
Ibu Fitri Mufidah	Ceperan 2/7 Jendi
Bapak Gatot Tri Widodo	Jl. Yudistira Iv Rt 3/4 Wnkrto
Bapak Karyawan Bam	Wonogiri
Ibu Lanny Nurhayati	Brumbung
Rere Klasik	Bantarangin, Bulusulur
Ibu Sumiyem	Mundu, Purworejo
Bapak Hamba Alloh	Ngadirojo
Bapak Agus Hedi Purwanto	Klumplit Karanganyar
Ibu Eni	Geneng  Purwosari
Ibu Nuryati	Salak 2/4 Giripurwo Wonogiri
Ibu Sri Wahyuni	Ngadirojo
Bapak Naryo	Pasar
Ibu  Menik	Krisak, Singodutan
Bapak Min	Wonogiri
Wr.  Yono	Mulia Hati
Warung Makan Podo Moro	Npc, Ngadirojo
Hamba Alloh	Mundu, Purworejo
Ibu Novi Buah	Psr Ngadirojo
Ibu Tini	Gayam Ngadirojo
Asysyifa	Giriwono
Bapak Muhammad Taufiq Bi	Semin Kulon 2/1 Purworejo
Bapak Pujianto	Bulusari 2/4 Bulusulur
Bapak Santoso	Manggung 3/1 Saradan Baturetno
Bapak Muhammmad Ferdian H	Kedungsono 3/6 Bulusulur
Ibu Fitri Mufidah Qq Wagiyo	Ceperan 2/7 Jendi
Ibu Lilis Setyowati	Dalan Gedhe 2/8 Sikoharjo Tirtomoyo
Bapak Tularno	Bulusari 2/3 Bulusulur
Bapak Fahru Romadhoni	Pocung 2/2 Mlokomanis Kulon
Bapak Haryono	Sambirejo 1/13 Wonokerto
Ibu Murdiyanti	Sumbersari 2/6 Purwosari
Ibu Miyatmi	Sukorejo 3/10 Giritirto
Bapak Mardiyatmo	Pokoh 2/3 Wonoboyo
Bapak Kukuh Putra Pangestu	Bakalan 1/12 Pagutan Manyaran
Ibu Lilis Nureni	Bulusari, Bulusulur
Bapak Heru Wiguna	Jurug Pokoh Kidul
Ibu Endang Dwi Lestari	Jetis 2/5 Wuryorejo Wng
Bapak Tri Efendi	Pudak 1/2 Beji Nguntoronadi
Ibu Ikaningsih	Tempurejo 1/6 Manjung
Ibu Heny Nurdyastuti	Jl Salak I No 17 1/4 Giripurwo Wng
Bapak Sri Widodo	Sumberejo 2/3 Purworejo Wng
Ibu Heny Puji Astuti	Cubluk 2/4 Giritirto
Bapak Iyan Gosan Nanda	Josutan 3/2 Kaliancar
Bapak Ade Putranto	Jatibedug 1/7 Purworejo
Ibu Iis Siti Aisyah	Kalmpisan 1/7 Kaliancar
Bapak Paryono	Mogok 2/1 Tanjung Juwiring
Bapak Eko Margiyanto	Sambirejo 2/13, Wonokerto
Bapak Wanto	Karang Talun 2/3 Pokoh Kidul
Bapak Giar Aldi R	Jati Marto 1/5, Ngadirojo
Bapak Aji Setyawan	Sambirejo 2/14 Wonokerto
Bapak Sutikno	Sumberejo 1/3, Wonokerto
Bapak Mohammad Harry S	Bulak 1/3 Nambangan
Bapak Adi Hermawan	Seneng 2/6 Giriwono
Bapak Nuzul Qoriyanto	Kedungringin 1/13, Giripurwo
Ibu Laras Satiti Handayani	Pakem Kidul 1/6 Sumberagung
Bapak Adi Suwito Qq Ppit Al Huda	Smpit Al Huda
Bapak Dastin Pangestu W	Karang Talun 2/3 Pokoh Kidul
Bapak Agus Arifin	Belik Jaten Selogiri
Bapak Giman 	Krisak, Singodutan
Bapak Riyanto	Pokoh Kidul
Ibu Naning Sri Rahayu	Brajan, Rt 1/5, Kaliancar,  Selogiri
Ibu Dwi Lestari	Wonogiri
Majelis Taklim Masjid Al Iklas	Banjardowo, Purworejo
Ibu Surati Binti Katimin	Wonogiri
Ibu Siyem	Ngadirojo
Ibu Mariyem	Ngadirojo
Ibu Iibu Naufal Nur	Mundu, Purworejo
Ibu Agustin	Ngadirojo
Angkringan 	Mulia Hati, Kaliancar
Wm Pak Rt	Mulia Hati, Kaliancar
Mie Ayam Bakso Pak Min	Krisak, Singodutan
Hamba Alloh	Selogiri
W.M.  Mbok Nik	Ketonggo, Ngadirojo
Wm Depan Npc	Ketonggo, Ngadirojo
Wm Nasi Liwet	Npc, Ngadirojo
Bapak Mahar	Ketonggo, Ngadirojo
Ibu Suji Haryatmi	Wonogiri
Bapak Bp. Katimin	Wonogiri
Bapak Azis Junaika Asianto	Wonogiri
Bapak Yana Yusnita Yasin	Wonogiri
Bapak Hamba Alloh	Pokoh Wonogiri
Bapak Bambang Arif	Gemantar, Selogiri
Ibu Alm.  Katinem	Kenteng Ngadirojo
Bapak Hamba Alloh	Sanggrahan, Giripurwo
Ibu Fitri Mufida Qq Resta Ayu Ditya	Ceperan 2/7 Jendi
Bapak Wartoyo 	Perum Siwani, Singodutan
Ibu Nuryaningsih	Sumberejo 2/3 Purworejo Wng
Ibu Ardhia Indah I	Kedungsono 4/6 Bulusulur Wng
Bapak Ilham Yuda Efendi	Joho Lor 3/5 Giriwono Wng
Ibu Renyta Adelia	Kedungringin 2/13 Giripurwo Wng
Bapak Awal Prasetyo N	Karangtengah 2/8 Jaten Slg
Ibu Siti Saridatun	Sanggrahan 3/8 Giripurwo Wng
Ibu Endah Wahyuningsih	Gerdu 2/5 Giripurwo
Bapak Setiyo Wibowo	Gondang Kulon 3/5 Purwosari
Bapak Paiman	Manggis 2/11 Ngadirojo Kidul
Ibu Wariyem	Lingkungan Ngersik 2/1 Beji Nguntoronadi
Ibu Indah Purnamasari	Turisari 3/8 Toriyo Bendosari
Bapak Dwi Yanto	Sambirejo 1/13 Wonokerto
Bapak Sigit Prasetyo	Wuryantoro Lor 3/2 Wuryantoro
Bapak Arif Wahyu Saputro	Sambirejo 1/4 Wonokerto
Ibu Aprilia	Tenongan 1/9 Jendi Selogiri
Bapak Bambang Setiawan	Pokoh 2/1 Wonoboyo
Bapak Supriyanto	Banaran 1/17 Genuk Wuryantoro
Bapak Warsono	Jurug 1/10 Pokoh Kidul Wng
Ibu Mariastuti	Sanggrahan 1/8 Giripurwo
Bapak Dwi Wiranto	Salak 2/4 Giripurwo Wonogiri
Ibu Ayu Pradityana	Kedungsono 3/6 Bulusulur
Bapak Hastopo	Jolomego 1/7 Sonoharjo
Bapak Jatu Prabowo	Jl. Salak 1 No 22 2/4 Giripurwo Wng
Ibu Rohani	Ngemplak 1/13 Ngadirojo Kidul
Bapak Catur Setiyanto	Jl. Salak 9  3/8 Giripurwo Wng
Bapak Indra Setiyawan	Jurutengah 5/4 Tasikhargo
Bapak Supriyono	Koripan 1/15 Genuk Harjo
Bapak Fajar Romasyah	Perum Siwani Sukses Singodutan
Bapak Bambang Arig S	Dukuh 2/6 Gemantar Selogiri
Ibu Diyah Ayu Setyaningsih	Kedungringin 1/12 Giripurwo
Ibu Tumini	Bauresan 3/1 Giritirto Wng
Bapak Misri	Banaran 3/10 Wonoboyo
Ibu Tian Egistasari	Semin Kulon 2/1 Purworejo
Ibu Dyah Ayuning Istiqomah	Petir 2/4 Pokoh Kidul
Ibu Desi	Kios Pasar Wng
Bapak Naryo	Bauresan, Giritirto
Bapak Joko Pramono	Gunung Wijil, Kaliancar, Selogiri
Raya Berkah Jaya	Kerdukepik, Giripurwo
Bapak Dani	Batas Kota, Giriwono
Bapak Iskandar	Sukorejo  Giritirto
Ibu Iin	Sukorejo  Giritirto
Bapak Alm. Bp. Darno Wiyono	Selogiri
Ibu  Ari	Giripurwo
Ibu Ngatiyem	Tenongan 1/9 Jendi Selogiri
Ibu Larsi	Tenongan 1/9 Jendi Selogiri
Ibu Bu Sum	Ngernak, Jatipurno
Ibu  Tanti	Gerdu, Giripurwo
Bapak Hanjaya	Tukluk, Ngadirojo
Bapak Tarso	Semin, Purworejo
Bapak Dodit Apriyan	Bulusulur Wonogiri
Ibu Dwi Murni/Wardi	Tangkluk Pare Selogiri
Bapak Agus Purwanto	Cubluk 1/4 Giritirto
Ibu Rini Susanti	Kedungsono 3/6 Bulusulur
Ibu Simi	Wonogiri
Bapak Hendra Arsyandi I	Kedungbanteng 1/4 Sendangijo Selogiri
Bapak Muhammad Febriyanto	Kaloran 4/8 Giritirto Wng
Bapak Fauzi Andrean	Cubluk 2/4 Giritirto
Bapak Pujianto	Perum Griya Purwosari Asri Blok D 06
Ibu Ida Wahyuni	Manggis 2/11 Nagdirojo Kidul
Ibu Rina Irawan	Bulusulur 1/2 Bulusulur
Bapak Rais Fathoni	Jarak Waleng 2/9 Waleng
Ibu Karti	Semin Kulon 3/1 Purworejo
Bapak Mulyadi	Seminding 1/1, Baturetno
Bapak Suyanto	Sambirejo 1/13 Wonokerto
Ibu Sukatni	Wuryantoro Lor 2/2, Wuryantoro
Bapak Ryan Apriyanto	Ngemplak 2/13 Ngadirojo Kidul
Bapak Budiyanto	Kajar 2/6 Pokoh Kidul Wng
Bapak Heri Setiawan	Tritis 2/4 Ngadiroyo Nguntoronadi
Bapak Sumadi	Pengkol 2/2 Pokoh Kidul
Bapak Wiwik Ariyanto	Jatibedug 5/7 Purworejo
Ibu Dessy Ayu Artika	Salak 2/3 Giripurwo Wng
Ibu Linda Yustianingsih	Pancuran 1/6 Kaliancar Slg
Bapak Rohmadi Hermina	Petir 2/4 Pokoh Kidul
Ibu Erna Ratnasari	Sambirejo 1/14 Wonokerto Wng
Bapak Mulyono Dwimulya	Bulusari 2/3 Bulusulur
Bapak Mukimin	Pondok Wetan 1/3 Pondok Ngadirojo
Ibu Nanik Rahmini H	Manggis 3/11 Ngadirojo Kidul
Bapak Ezyanto Dwi Cahyono	Geneng 3/12 Purwosari
Ibu Dewi Fatikasari S	Sumbersari 1/6 Purwosari
Bapak Eko Yulianto	Sumberejo 3/3 Purworejo Wng
Bapak Miftah Eko Prasetyo	Semin Kulon 2/1 Purworejo
Bapak Fedeus Bellaga Paska P	Wonokarto 1/4 Wonokarto
Bapak Indra Dwi Cahyono	Sukorejo 2/10 Giritirto
Koperasi Siswa Smp N 1	Wonogiri
Ibu Sunarti	Kantin Smpn 1 Wng
Ibu M. Deni	Kantin Smpn 1 Wng
Ibu  Iin	Kantin Smpn 1 Wng
Ibu Atmisari	Kantin Smpn 1 Wng
Ibu Eri Setyaningsih	Sanggrahan
Bapak Mursid Ariyadi	Jl Sadewo Iv Wonokarto
Bapak Fery Sandria Purnama	Ngringin Temulus Keloran
Bapak Wahyu Adhi Nugroho	Pucangwolu Wonogiri
Bapak Akif Atolah	Semin Wetan
Bapak Suyatno	Kedungbanteng 1/4 Sendangijo Selogiri
Bapak Wartono	Sambirejo Wonokerto
Bapak Satrio Tabah M	Pulorejo Nambangan Selogiri
Bapak Hermawan Rukmi W	Perum Giri Asri Singodutan
Bapak Wahyu Bramistian 	Kerdukepik
Ibu Roch Sariningsih	Ngadirojo
Bapak Zanuar Wisnu K	Ngadirojo
Bapak Pasha Jati	Wonogiri
Staraja Coffee	Ngadirojo
Ibu Wahyuning S	Semin Wetan
Ibu Yatni Nur H	Semin Kulon
Bapak Harmoko Triaji	Pokoh Wonoboyo
Ibu Parwanti	Sanggrahan
Ibu Prihatin	Semin Wetan, Purworejo
Ibu Fitri Mufidah	Jendi Selogiri
Ibu Retno Kawuri	Salak, Giripurwo
Ibu Yunita Dewi P	Kaloran , Giritirto
Bapak Suyono	Gerdu, Giripurwo
Ibu Suparni	Kaloran , Giritirto
Bapak Tufi L	Wonogiri
Ibu Ida Rohmana	Klerong
Abata	Ngadirojo
Ibu Renita Adelia	Giritirto
Bapak Alm Sularto	Karangtalun
Bapak Abdillah	Sumberejo
Ibu Mega Dewi 	Bauresan
Bapak Sukijo Sumarni	Jomboran, Jaten, Selogiri
Bapak Dimas	Solo
Bapak Marno	Salak
Ibu Sukesti Nuswantari	Selogiri
Bapak Suyoko	Perum Giri Asri Singodutan
Ibu Esti Khomariyah	Manjung Kulon 3/4
Bapak Damar 	Ngadirojo
Ibu Septina Aryani	Perum Greenlake
Ibu Tri Widiastuti	Solo
Ibu Dr. Tuty Yuniati	Donoharjo
Ibu Alm Endangsih	Kios Pasar Wng
Mas Roh	Gayam Ngadirojo
Bapak Junaedi	Pokoh, Wonoboyo
Ibu Sadiyem	Gerdu 1/5
Ibu Nanik Yuliati	Gerdu 2/5 Giripurwo
Ibu Sri Wandini	Gerdu 2/5 Giripurwo
Ibu Ika Yuliani	Gerdu 2/5 Giripurwo
Ibu Yuning/Agus Heri Santoso	Salak, Giripurwo
Ibu Sri Suyatni	Bauresan 4/2, Giritirto
Ibu Nurhayati	Bauresan 3/1, Giritirto
Ibu Anik Sudarmani	Kajen 2/10, Giripurwo
Ibu Siti Suyani	Kajen 2/10, Giripurwo
Ibu Siti Rahayu	Kajen 1/11, Giripurwo
Ibu Nunuk Sri Purwani	Bauresan 3/2, Giritirto
Ibu Sukamto	Bauresan 2/2, Giritirto
Ibu Sri Latifah	Cubluk 2/4, Giritirto
Ibu Iibu Karno/Kaino	Bauresan 4/2, Giritirto
Ibu Sugiatni	Bauresan 2/2, Giritirto
Ibu Sri Mulyani	Bauresan 4/1(Sate Saimo), Giritirto
Ibu  Piah	Kajen 2/10, Giritirto
Ibu Marti Ningsih	Kajen 1/11, Giripurwo
Bapak Ari Onang	Kajen 2/2, Giripurwo
Bapak Auzan Dhika Arfadly	Waduk Ngadirojo
Ibu Kani	Jurug, Pokoh Kidul
Ibu Maryati	Semin Wetan, Purworejo
Ibu Mulyani	Ngernak Kembang Jatipurno
Bapak Heru Erwanto	Wonokarto
Raya Petshop	Kerdukepik, Giripurwo
Ibu  Eko	Ketonggo, Ngadirojo
Warung Makan Masjid	Ketonggo, Ngadirojo
Ibu Nur Hidayati	Manggis, Ngadirojo
Ibu Ani Endang Sriningsih	Wonogiri
Bapak Harsono	Wonokarto
Ibu Karsini	Semin Wetan, Purworejo
Ibu Ina Nur Khasanah	Pule Jatisrono
Ibu Suparti	Shelter, Wonogiri
Bapak Dr Martanto	Donoharjo
Bapak Irwan	Giripurwo
Ibu Cici	Giripurwo
Rosi Cell 	Ngadirojo
Ibu Yatmi	Jatibedug
Bapak Purnomo	Kajen, Giripurwo
R.M.  Padang Minang Raya	Bulusulur
Ibu Ani	Gerdu, Giripurwo
Ibu Kurnia Sukma	Pdam
Ibu  Bambang	Kantin Smpn 1 Wng
Ibu  Eki	Kantin Smpn 1 Wng
W.M Bundar	Jurug, Pokoh Kidul
Ibu Anik	Tandon Pare
Bapak Eko Supendi	Jatirejo 2/8 Wonoboyo
Ibu Nadiyah	Bekasi
Ibu Yatini	Semin Wetan, Purworejo
Geprek Cantik	Npc Ketonggo, Ngadirojo
Ibu Iibu Nunik	Banaran 3/10 Wonoboyo
Ibu  Lilik 	Pasar Wonogiri
Bapak Merista Adi Prasetyo	Manjung Kulon 3/4, Purwosari
Ibu Dewi Wahyuni	Pelang 1/8 Kerjo Kidul Ngadirojo
Bapak Agus Prihatin Budi Djaja	-
Ibu Hety Wulandari	Semin Kulon Purworejo
Ibu Etik Sulistiawaty	Wonogiri
Bapak Lardi	Pokoh Wonoboyo
Ibu Rafika Sari	Sanggrahan Giripurwo
Ibu Suharti	Kantin Smpn 1 Wng
Bapak Krisyanto	Jatisrono
Kotak Amal Bmt Amal Muslim	Wonogiri
Bapak Ari Tri Sakti Atmoko	Salak 2/4 Giripurwo Wonogiri
Bapak Reza	Sendangsari, Giriwono
Ibu Syifa	Sendangsari, Giriwono
Ibu Mariyati	Semin Wetan 2/2 Purworejo
Masjid Ash Sholihin	Wonokarto
Toko Ika	Mundu, Purworejo
Ibu  Susi	Ngerco, Ngadirojo Lor
Toko Pandu	Pokoh, Wonoboyo
Ibu Dwi Handayani	Krisak, Singodutan
Ibu Maylani Dyah Sulistyowati	Sambirejo 1/3 Wonokerto
Ibu Dayani	Ngasinan 2/1 Wonoharjo
Ibu Hesti Sutarmi	Banaran 2/11 Wonoboyo
Bapak Doni Sapto	Ngresik 1/1 Beji Nguntoronadi
Bapak Iwan Susilo	Sanan 1/1 Waru Slogohimo
Bapak Andri Mulyono	Bulusari 1/3 Bulusulur
Bapak Agus Budi Setyawan	Sambiroto Pracimantoro
Bapak Dwi Azariawan	Sumbersari 3/6 Purwosari Wonogiri
Tahu Kupat	Donoharjo
Pradana Cell	Donoharjo
Warung Makan Padang	Tunggul Giriwono
Warung Makan Hidayah	Joho Lor Giriwono
Warung Ketucky	Giriwono
Ibu Yuli	Joho Kidul, Giriwono
W.M Pelangi	Wuryantoro
Hik Tono	Wuryantoro
Mie Ayam Bakso Maharini	Wuryantoro
Ibu Tini	Wuryantoro Lor
W.M Sederhana Bu Nuri	Donoharjo
Ibu Tri Yuniarti	Pokoh 1/2 Wonoboyo
Ibu Janiem	Gerdu, Giripurwo
Toko Berkah Pakan	Sonoharjo
Mieso Bang Satiman	Tunggul Giriwono
Ustadzah Erminawati	Smkit Al Huda, Giriwono
Ustadzah Nurul Hidayah	Smkit Al Huda, Giriwono
Ustadzah Shofia	Smkit Al Huda, Giriwono
Ustadzah Ayu	Smkit Al Huda, Giriwono
Ustadzah Ririn	Smkit Al Huda, Giriwono
Bapak Andri Saputro	Belik Dawung RT 1/7, Puh Pelem
Warung Makan Padang	Banaran, Wonoboyo
Zia Petshop	Pokoh, Wonoboyo
Mie Ayam Bakso	Krisak Atas Al Maida, Singodutan
Soto Tengah Gunung	Jetis Wuryorejo
W.M Ayam Bakar 	Mlopoharjo Wuryantoro
Counter Sidoseneng	Wuryantoro Pasar
Mie Ayam Anugrah	Donoharjo
Koperasi Smk It Al Huda	Giriwono
W.M.  SotoSurat	Donoharjo
Ibu Dwi Hartanti	Jurug, Pokoh Kidul
Bapak Kepala Sekolah	Smkit Al Huda, Giriwono
Ibu Ellistia	Kantin Smpn 1 Wng
Ibu Suprapti	Kantin Smpn 1 Wng
Mie Ayam Bakso Jay	Wuryantoro
Laris Plastik	Kajen Giripurwo
Raya Komputer	Giriwono
Bapak Fajar Romadhoni	Pokoh Wonoboyo
Tpq Arrohman	Manggis Ngadirojo
Najwa Busana	Krisak Singodutan
Majelis Taklim Muslimah Sekar Jalak	Joho Lor Giriwono
Ibu Almh. Sukatmi	Krisak Kulon Singodutan
Masyarakat Lingkungan Sanggrahan	Sanggrahan Giripurwo
Bapak Suryanto	Jetis Sukoharjo
Ibu Riyanti	Sukorejo Giritirto
Ibu Fadila Kurnia Sari	Sumberejo Purworejo
Ibu Ahnaf Nuha Abdillah	Bero Manyaran
Ibu Siti Maindarsih	Kedungringin Giripurwo
Ibu Malida Hesti Pratiwi	Brumbung Kaliancar
Ibu Murtantini	Randusari Ngadirojo Kidul Ngadirojo
Bapak Rofi Muhammad Dzakir A	Brubuh Ngadirojo Lor
Ibu Wiwik Prayugi	Ngasinan Sendangsari Giriwono
Ibu Yanti	Pokoh Wonoboyo
Ibu Resti Widiarni	Semin Purworejo
Majelis Taklim Al Busro	Pokoh Wonoboyo
Majelis Taklim Perum Emerald 3	Semin Purworejo
Jamaah Mushola As Salam	Semin Purworejo
Ibu Yessi Novia	Karangtalun Pokoh Kidul
Jamaah Al Karimah	Pokoh Wonoboyo
Jamaah Nur Huda	Mojoroto Wonoboyo
Ustadz Eko Yulianto	Smkit Al Huda, Giriwono
Ibu Amin Trisnawati	Cubluk Giritirto
Bapak Sigit Prasetyo	Wuryantoro
Bapak Suwandi	Donoharjo, Wuryorejo
Bapak Fajar Romansyah	Perum Siwani Sukses Singodutan
Bapak Suprianto	Genukharjo Wuryantoro
Pipit	Petirsari Pracimantoro
Heny Puji Astuti	Cubluk Giritirto
Ibu Lanny Nurhayati	Brumbung, Kaliancar
Ibu Sinta	Kedungringin 1/13, Giripurwo
Bapak Heri Yulianto	Gerdu, Giripurwo
Ibu Dhanik Riastuti	Wonogiri
Bapak Rudi Adi Suwarno	Sragen
Bapak Handi Prasetyo	Sumberejo Wuryantoro
Ibu Lilis Suryani	Bulusulur Wonogiri
Ibu Martini	Kedungringin, Giripurwo
Muhammad Aril	Wonogiri
Novi Andri	Wonogiri
Roni	Wonogiri
Muhammad Rizky	Krisak Singodutan
Ibu Soegiyatmi	Sambirejo Wonokerto
Mariatul Qibtiyah	Sayangan Pule Selogiri
Bapak Anggi Imam Prasetya	Krisak Kulon Singodutan
Bapak Agung Prasetyo	Sumberejo Purworejo
Ibu Nofia Adesta Ramadani	Kaliancar Selogiri
Ustadz Roni Juniawan	Smkit Al Huda, Giriwono
Griya Petshop	Selogiri
Bapak Heri Teguh H	Salak Giripurwo
Kristina Dwi Irwanti	Jurug Pokoh Kidul
Abdul Hanif	Smkit Al Huda, Giriwono
Mbak Eka	Kedungringin Giripurwo
Toko Via-vio	Sumberejo, Purworejo
Bapak Purwanto	Segawe Purwosari
Ibu Syitha Luckytasari	Mundu, Purworejo
Ibu Dwi Hartanti	Dungrejo Wonokerto
Ibu Alifa Marta S	Pule Selogiri
Bapak Yoni Cahyo W	Perum Siwani Sukses Singodutan
Ibu Amung Tri H	Sanggrahan Giripurwo
Ibu Suyanti	Ngadirojo Kidul , Ngadirojo
Mie Ayam Pak Man	Giriwono
Bapak Sunarmo	Nguntoronadi
Bapak Yuna Panji Surya	Pokoh Kidul
Bapak Marsono Hadi S	Wonokerto
Bapak Warseno	Semin Purworejo
Ibu Tri Apriliani	Jatirejo Wonoboyo
Bapak Narmin	Purwantoro
Bapak Sarimin	Nguntoronadi
Bunda Hesti	Wuryantoro, Ploso
Pak Suratno	MAN Wonogiri
Mbak Parni	MAN Wonogiri
Bu Kasmiati	Jurug, 02/10 Pokoh Kidul, Wonogiri
Pak Sutarno	Kedungdadap, 01/05, Eromoko, Wonogiri
Bu Devi Niah 	Timang Wetan, 01/02, Wonokerto, Wonogiri
Pak Dadang Nur Hudiyanto	Cubluk, 02/04, Giritirto, Wonogiri
Bu Fitri Mufidah QQ Ilham Qomarudin	Ceperan, Jendi, Selogiri
Bu Fitri Mufidah QQ Purnaningsih	Ceperan, Jendi, Selogiri
Pak Suyanto	Perum Citra Jaya 7, 04/07, Purworejo, Wonogiri
Pak Wahyudi 	Geneng, 01/11, Purwosari, Wonogiri
Muhammad Abdurohman S	Kuyudan Baru, 03/05, Makam Haji PKH
Drs. Baktiarto	Jl. Salak 3, 02/03, Giripurwo
Bapak Sumardi	Jomboran, Jaten, Selogiri
Pak Subudi Murod	Jl. Salak 3, 04/03, Giripurwo
Bu Fitri Mufidah QQ Susilo	Ceperan, Jendi, Selogiri
Bu Murdiyanti QQ Sisugastri	Sumbersari 2/6 Purwosari
Pak Dicki Bayu Ramadan	Bauresan,02/02, Giritirto
Bu Fitri Mufidah QQ Sarya A	Ceperan, Jendi, Selogiri
Bu Erni	Joho Lor, Giriwono, Wonogiri
Ustadz Ahmad	Smkit Al Huda, Giriwono
Resto Oseng Kepala Kambing	Joho, Giriwono
Bu Lilik 	Pasar Wonogiri
Bpk Rizal Imam Mustafa	Ngadirojo Kidul , Ngadirojo
Pak Davit	Sumberejo
Pak Tjiptoning	Wuryantoro, Wonogiri
Ibu Warmi	Joho, Giriwono
Ibu Supartini	Wuryantoro
Ibu Sri Hastuti	Banaran
Bapak Abdullah Isnaini	Joho Kidul, Giriwono
Alm Parto Sentono Bin Irodipono	Mojopuro, Wuryantoro
Ibu Dewi Rahma wati	Giriwono
Bapak Sugeng Sapardi	Purwosari
Bapak Ahmad Soegandhi	Wonoboyo
Ibu sihwanti	Jurug Pokoh Kidul
Bapak Sri Yono	Ngadirojo
Ibu Yesika Kurnia Ningtyas	Purwosari
Ibu Deny Nurhayati	Giriwono
Bapak Ichsan Suparmanto	Pucangwolu Wonogiri
Bapak Sujimin	Sendangsari, Giriwono
UJKS Kossuma	Ngadirojo
Bapak Demriadi	Pokoh Wonoboyo
Agus Riyanto	Bulusulur Wonogiri
Agus Suyatmo	Wuryantoro
Suci Mulyadi	Purworejo wonogiri
Bapak Kastanto	Wuryantoro
Bapak Davit	Sumberejo
Ibu Etik Rahmawati S. Farm	Jl diponegoro Wonoboyo wonogiri
Bapak Slamet Darmanto	Wuryantoro
Sri Rahayu	Bulusulur
Ibu Sutini	Baturetno
Bapak Sujarno	Nguntoronadi
Bapak Sutopo	Wonokarto
Bapak Fahrudin Kurniawan	Wonokarto
Ibu Emi Budi A	Wonoboyo
BMT AMAL MUSLIM	Wonogiri
Ibu Harni	Sumberejo, Purworejo
Giri Komputer 	Ngadirojo
Hamba Allah 	Pokoh Wonogiri
Bapak Iswanto	Wuryantoro
Mutiara Juice	Ngadirojo
Jamaah masjid al Ikhlas	Barengan, Jaten
Toko SRC Garuda	Wuryantoro Lor
Ibu Darmi	Ngadirojo
Ibu Siti	Wuryantoro
Bapak Iwan 	Jomboran, Jaten, Selogiri
Sdr. Shika	Jomboran, Jaten, Selogiri
Ibu Poniyem	Jomboran, Jaten, Selogiri
Ibu Sunarmi	Jomboran, Jaten, Selogiri
Bapak Rusminto	Jomboran, Jaten, Selogiri
Hamba Allah 	Jomboran, Jaten, Selogiri
Bapak Gito	Jomboran, Jaten, Selogiri
Bu Sumarti 	Kaloran, 01/07, Giritirto, Wonogiri
Ibu Yosi	Klemut, Bulusulur
Bapak Muhammad Rosid	Wonokarto
Bapak Agus Susilo	Ngadirojo
Bapak Gito	Barengan, Jaten
Bapak Joko Rianto	Ngrangkok Sumberejo, Purworejo
Ibu Sri Sumarni	Barengan RT 3/8, Jaten Selogiri
Bapak Katno	Jomboran, Jaten, Selogiri
Bapak Joko Sriyanto	Jomboran, Jaten, Selogiri
Mbak Salma Nur Arsyah	Mojokerto
Ibu Sriyatmi	Pare, Ngadirojo
Ibu Sumarni Tri Hartanti	Sanggrahan, Giripurwo
Ibu Hadmini	Barengan RT 3/8, Jaten Selogiri
bu tutik	Barengan RT 3/8, Jaten Selogiri
Ibu Kamti	Barengan RT 3/8, Jaten Selogiri
Sdr. Radit / Ibu wiwik	Barengan RT 4/8, Jaten Selogiri
Ibu Wiwik Wiyanti	Barengan RT 3/8, Jaten Selogiri
Bapak Radin	Barengan RT 3/8, Jaten Selogiri
Bapak Suyatmo	Barengan RT 3/8, Jaten Selogiri
Bapak Wiyadi	Barengan RT 3/8, Jaten Selogiri
Ibu Ninik Hiyastini	Joho Lor Giriwono
Ibu Sri Suyatmi	Bulusulur
Bapak Agus Setiawan	Semin Purworejo
Cilok Bu Wilis	Joho Kidul, Giriwono
Seblak Mbak Rani	Joho Lor Giriwono
Sdr. Anna 	Smkit Al Huda, Giriwono
Sdr. Desta Lia	Wuryantoro
Ibu Mesrawati	Wonokerto
Alm. Bp. Tugimin	Jomboran, Jaten, Selogiri
Sdr. Aisha Izzatun	Jomboran, Jaten, Selogiri
Bapak Tunggal	Jomboran, Jaten, Selogiri
Mbak Dwi Palupi	MAN Wonogiri
Sdr. Daru Zainul	Wuryantoro Kidul
Ibu Hesti	Keblokan Sendangijo
Ibu Sriwati	Keblokan Sendangijo
Bapak Joko Sriyanto - Supatmi	Jomboran, Jaten, Selogiri
Bapak H. Sri Wiyono	Keblokan Sendangijo
Toko Adiba	Brumbung, Kaliancar
Ibu Anny	Pokoh Wonoboyo
Ibu Fitrah	Keblokan Sendangijo
Wali Murid SMK IT Al Huda	Wonogiri
Pak Selamet	Gerdu, Giripurwo
Muhari Motor	Selogiri
Wali Siswa Mikail	Smkit Al Huda, Giriwono
Wali Siswa Alfidan	Smkit Al Huda, Giriwono
Bu Istuti	Banaran, Genukharjo, Wuryantoro,
Mb. Salwa Azizah	Jarum, Sidoharjo
Bu Darsini	Semin, Purworejo
Bu Painah	Semin, Purworejo
Sdr. Yuly Wahyuningsih	Joho Lor Giriwono
Sdr. Isma	Tare Kerjo Lor Ngadirojo
Ibu Marsi	Pondok Ngadirojo
Ahmad Yusuf	Joho Lor Giriwono
Ibu Lanny Nurhayati	JL Dewi Satika 1/7 Wonokarto
bu dwi nurmini	tangkluk
bu rini puji astuti	wali smk it alhuda
bu dewi 	wali smk it alhuda
bu siti 	wali smk it alhuda
bu saikem 	wali smk it alhuda
bu ambar 	wali smk it alhuda
bu kurni 	wali smk it alhuda
bu marmini 	wali smk it alhuda
bu yuni 	wali smk it alhuda
bu iren 	wali smk it alhuda
bu sarni 	wali smk it alhuda
bu hanifa 	wali smk it alhuda
mbah suki 	wali smk it alhuda
ibu tukini 	wali smk it alhuda
pak sipar	wali smk it alhuda
mbah saman 	wali smk it alhuda
bapak supartono 	wali smk it alhuda
bapak sutarno 	wali smk it alhuda
Bapak Suyoto	Wonogiri
Jamaah Al ma'tsurot	Giripurwo
Sdr. Adit Wahyudi	Smkit Al Huda, Giriwono
Sdr. Bayu Indra Purnama	Manyaran
Sdr. Mila Adila 	Girimarto
Bu Sri Wahyuni	Barengan RT 3/8, Jaten Selogiri
Bapak Winoto	Smkit Al Huda, Giriwono
Ibu Tuginem	Smkit Al Huda, Giriwono
Sdr. Sinta	Smkit Al Huda, Giriwono
Bu Surati	Semin, Purworejo
Bu Yuyun	Pokoh Wonoboyo
Almh Wasiyau & Alm Tugiyo	Mojopuro, Wuryantoro
UPA wuryantoro	Wuryantoro Kidul
Bu Diarti	Pokoh
Jama'ah Jomboran	Jomboran, Jaten, Selogiri
Dwi Hatmoko	Wuryantoro
Edy Yuwantoro	Purwantoro
Yohaniatun	Joho Lor
Slamet	Berbarengan, Selogiri
Swarmi	Berbarengan, Selogiri
Jamaah Masjid al Busro	Pokoh
Toni Budi Cahyono	Sambirejo, wonokerto, Wonogiri
Linda Wahyu Hana	Jatiroto
Rahmat Musthofa	Baturetno
Rian Setyanto	Manjung Wetan
Ikem	semin
Majelis Khodijah	Jatirejo, Wonoboyo
Eka Suryana Putra	Kedukepik
Eko Mulianto	Wonogiri
Sunar	grand phone, Kedungringin
Sudigdo Adi Prabowo	Wonokarto
Sunarti	Perum Griri Asri, Selogiri
Wondono	Salak
Sarni	Bekasi, Jawa Barat
Ibu Patmawati	Klaten
Pandi (BPRS Dana Amanah)	Surakarta
Dwi Rohmani	Bulursulur
Destri	Sukoharjo
Sri Rochayah	Kedungringin
Mulyadi	Baturetno
Gatot Kuncoro	Gondang Wetan
Sulasmi	Jomboran, Jaten, Selogiri
Dewi Retno Sari	Selogiri
Cicik Purbandini	Kaloran
Triyanto	Kajen
Didik Hari Purwadi	sukoharjo
Arisa Tanjung Sari	Sukoharjo
Imron Abbas	Sukoharjo
Iqbal Rasyid Habibi	Sukoharjo
Ibu Suparti	Keblokan Sendangijo
W.M Ibu Yanti	Timang
Mie ayam Timang	Timang
Hamba Allah 	Joho Lor, Giriwono, Wonogiri
Mbak Ika	Kedungringin
Bu Anik	Banaran, Wonoboyo
Bapak Mujib	Jurug Pokoh Kidul
Jamaah Kahfi	Brajan, Selogiri
Bu Yayuk	Perum Pokoh Kidul
Nadiya Ulfa	Wuryantoro
Ibu Sumarsih	Tahu - Pasar, Wonogiri
bu sami 	wali smk it alhuda
Bu Martin	Sanggrahan
Ibu Elusmuddah Yuliana	Cangkring
Ibu Yatmi Nur	Semin
Bapak Aril	Wonokarto
Ibu Novi	Wonokarto
Bapak Roni	Wonokarto
Ibu Rita	Sanggrahan
Ibu Siti Rohani	Selogiri
Bapak Ponomin	Sumberejo, Purworejo
PAUD AL MUJAHIDIN	BANARAN, WONOBOYO
Bu Anny Sutarni	Pokoh
Bu Giyatni	Semin
Jamaah Liqo' Semin	Semin
Ibu Kademi	wonogiri
Ibu Gunarni	Semin Kulo
UPA Khodijah	Jatirejo Wonoboyo
Ibu Sri Maryuni	Gerdu
Ibu Sri Wahyuni	Sumberejo
UPA Sabtu Pagi	Semin
SDR. Toni Budi Cahyono	Sambirejo
Bapak Tarno	Sanggrahan Giripurwo
Ibu Tri Susilaningsih	Kerdukepik
Ibu Parni	Semin
Saudara Safira	SMKIT Al Huda Wonogiri
Ibu Ida	Wuryantoro
Wm Ibu Nanik	Joho
Mie Ayam Tunggul	Tunggul Giriwono
Ibu Suamarni	Perum Intro Jaya 7
Saudara Shinta	SMKIT Al Huda Wonogiri
Saudara Nurul	Purwantoro
Saudara Luthfi	Jatisrono
Mama Alin	wali smk it alhuda
Bu Tumini	wali smk it alhuda
Saudara Muna	SMKIT Al Huda Wonogiri
Wali SMKIT	SMKIT Al Huda Wonogiri
Suyadi	Sanggrahan
Devi Kurniawati Putri	Kaloran
Rohmad Dwi Santoso	Sukorejo
Hestiawati 	Wuryantoro
Heri Yulianto	Joho Lor
Sulardi	Pokoh
Wiyarti	Sumbersari
Suwandi	Giriwono
Endar Rismono	Klampisan
Jilan Luthfiyah	Joho Kidul, Giriwono
Sri Mulyani	Krisak Wetan
Kasto	Tanjung
Vio Julianto	Pohpener,Genawang,Ngadirojo
Larno	Ngaglik,wuryantoro
Heri Setyawan	Mlangse Lor,Pracimantoro
Zanu Ari Setyabudi	ban Kidul,Baturetno
Aris Sutikno	Kedung Banten
Rofi' Muhammad DA	Brubuh Ngadirojo Lor
Wahyudi	Kedung Banteng
Hanifah	Ngemplak
Fitri Mufidah QQ Teguh Wiyono	Ceperan Selogiri
SDR.Octayiana Pramawati	Giripurwo
Sri Wahyuni	Sumberjo
SDR. Bagus Pribadi	Giripurwo
Ibu Ngatmi	Krisak
Ibu Painah	Semin
Ibu Purwani	Tunggul Giriwono
Sdr. Hasna Rosida	Donoharjo
Ibu Mujiati	Semin Kulon
Bapak Feri Supriyanto	Semin
Ibu Roni Sulistyo	Krisak Kulon Singodutan
Ibu ibu Ana Qunsa Salon	Pasar Krisak, Singodutan
Ibu Erna Ratnasari	Sambirejo
Ibu Sunarti	Perum Giri Asri Singodutan
Toko Ibu Nunung	Pokoh
Ibu Ernilia	Bulurejo Ngadirojo
Ibu Sugiyarsi	Pokoh
Ibu Santi binti Tio	Semin
Ibu Ita Usti Yani	Sambirejo Wonokarto
Ibu Hudayaningsih	Perum Griya Cipta Laras
Sdr Winda Eka Putri	Perum Griya Cipta Laras
Ibu Sri Wahyuningsih	Sanggrahan
Ibu Arum Setyawati Nur Cahya Ningsih	Sanggrahan
Bapak Alif	Kedungsono
Ibu Sri Wahyuni	Joho Lor Giriwono Wonogiri
Bapak Topik Prabowo	Karangtalun
Ibu Ulva	Timang Wetan, 01/02, Wonokerto, Wonogiri
Ibu Hesti Putri	Bulusulur
Ibu Utari	Kerdukepik 4/2, Giripurwo, Wonogiri
Widi Sutrisno	Wonokerto
Ibu Dwi Hartanti	Jurug
Lestari	Pokoh 2/4, Wonoboyo
Ibu Sri Wahyuni	Kedungringin
Narso	Sendangsari, Giriwono
Ibu Sulasmi	Salak 2/3 Giripurwo, Wonogiri
Ibu Erny Wijayanti	Godean 5/2 Sendang, Wonogiri
Ibu Wahyu Tri Cahyaningsih	Bauresan 3/1 , Giritirto, Wonogiri
Ibu Maya Kusmiatun	Rejosari 2/5 Gunung Lor
Majelis Ta'lim Ar Rohmat	Geneng Purwosari
Mbah Suwarsih	Joho Lor
UPA Pak Bambang	Purwantoro
Ahmad Sarbani	Kedung Jati
Ita Listiyani	Sambirejo
Ibu Zub	Wuryantoro
Ibu Patmi	Wuyantoro
Ibu Rusmini	Manjung
Mbah Suwarsih	Joho
Ibu Ary Istuti	Pokoh
SDR Yusuf Maulana	Takluk, Pule, Selogiri
Bu Karni	Semin Kulon
Ibu Thessa Pratami Arumsari	Pokoh, Wonoboyo
Ibu Eni	Purwosari
Hamid Noor Yasin	Bulusulur, Wonogiri
Ibu Wuryani	Banjardowo, Purworejo
Mas Anton	Krisak
Kayyisah Anati Muzayanah	Kerdukepik
Bu Endang	Sonoharjo
Pak Karmin	Sonoharjo
Pak Wibowo	Sambirejo
Lilik Ismurtanto	Pokoh
Sri Mulyani	Perum Purwosari
Ibu Siti	Wuryantoro
Bu Martin	Sanggrahan
Ibu Yosi	Klemut, Bulusulur
Bu Anny Sutarni	Pokoh
Ibu Sri Sumarni	Barengan RT 3/8, Jaten Selogiri
Ibu Hadmini	Barengan RT 3/8, Jaten Selogiri
Bapak Suyatmo	Barengan RT 3/8, Jaten Selogiri
Ibu Wiwik Wiyanti	Barengan RT 3/8, Jaten Selogiri
Bapak Radin	Barengan RT 3/8, Jaten Selogiri
Ibu Kamti	Barengan RT 3/8, Jaten Selogiri
Bu Sri Wahyuni	Barengan RT 3/8, Jaten Selogiri
bu tutik	Barengan RT 3/8, Jaten Selogiri
Bapak Wiyadi	Barengan RT 3/8, Jaten Selogiri
Sdr. Radit / Ibu wiwik	Barengan RT 4/8, Jaten Selogiri
Bapak Gito	Barengan, Jaten
Bapak Gito	Jomboran, Jaten, Selogiri
Ibu Poniyem	Jomboran, Jaten, Selogiri
Ibu Sunarmi	Jomboran, Jaten, Selogiri
Bapak Rusminto	Jomboran, Jaten, Selogiri
Hamba Allah 	Jomboran, Jaten, Selogiri
Sdr. Shika	Jomboran, Jaten, Selogiri
Bapak Katno	Jomboran, Jaten, Selogiri
Bapak Joko Sriyanto	Jomboran, Jaten, Selogiri
Bapak Iwan 	Jomboran, Jaten, Selogiri
Bapak Sukijo Sumarni	Jomboran, Jaten, Selogiri
""".strip()

def normalize(name):
    """Normalize name for matching: lowercase, strip whitespace, remove extra spaces."""
    n = name.strip().lower()
    n = re.sub(r'\s+', ' ', n)
    return n

def parse_data(data_str):
    """Parse tab-separated name\talamat lines, return list of (nama, alamat)."""
    result = []
    for line in data_str.split('\n'):
        line = line.strip()
        if not line or '\t' not in line:
            continue
        parts = line.split('\t', 1)
        nama = parts[0].strip()
        alamat = parts[1].strip() if len(parts) > 1 else ''
        if nama and alamat and alamat != '-':
            result.append((nama, alamat))
    return result

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Get all donatur
    rows = conn.execute("SELECT id, nama, alamat FROM donatur ORDER BY id").fetchall()

    # Build lookup: normalized DB name → list of (id, nama, alamat)
    db_lookup = {}
    for r in rows:
        key = normalize(r['nama'])
        if key not in db_lookup:
            db_lookup[key] = []
        db_lookup[key].append({'id': r['id'], 'nama': r['nama'], 'alamat': r['alamat']})

    # Parse user data
    user_data = parse_data(DATA)
    print(f"Total data alamat dari user: {len(user_data)}")
    print(f"Total donatur di DB: {len(rows)}")

    # Track updates
    updated = 0
    skipped_already = 0
    not_found = []

    # For each user entry, find matching DB record and update if alamat is NULL
    for nama, alamat in user_data:
        key = normalize(nama)

        if key in db_lookup:
            for entry in db_lookup[key]:
                if entry['alamat'] is None or entry['alamat'] == '' or entry['alamat'] == 'None':
                    conn.execute(
                        "UPDATE donatur SET alamat = ? WHERE id = ?",
                        (alamat, entry['id'])
                    )
                    updated += 1
                    print(f"  OK [{entry['id']}] {entry['nama']} -> {alamat}")
                else:
                    skipped_already += 1
        else:
            not_found.append((nama, alamat))

    # Also try matching old-format names (without prefix) for records 1-207
    # DB: "Anny Sutarni" vs User: "Bu Anny Sutarni"
    PREFIX = ['ibu ', 'bapak ', 'bu ', 'pak ', 'sdr. ', 'sdr ', 'saudara ', 'mbak ', 'mas ', 'ustadz ', 'ustadzah ']

    remaining = []
    for nama, alamat in not_found:
        found = False
        key = normalize(nama)

        # Try stripping prefix from user name
        stripped = key
        for p in PREFIX:
            if stripped.startswith(p):
                stripped = stripped[len(p):].strip()
                break

        # Search all DB records for match
        for db_key, entries in db_lookup.items():
            db_stripped = db_key
            for p in PREFIX:
                if db_stripped.startswith(p):
                    db_stripped = db_stripped[len(p):].strip()
                    break

            if stripped == db_stripped:
                for entry in entries:
                    if entry['alamat'] is None or entry['alamat'] == '' or entry['alamat'] == 'None':
                        conn.execute(
                            "UPDATE donatur SET alamat = ? WHERE id = ?",
                            (alamat, entry['id'])
                        )
                        updated += 1
                        print(f"  OK [{entry['id']}] {entry['nama']} <- (fuzzy) {nama} -> {alamat}")
                        found = True

        if not found:
            remaining.append((nama, alamat))

    conn.commit()

    # Count how many still have NULL alamat
    null_count = conn.execute("SELECT count(*) FROM donatur WHERE alamat IS NULL OR alamat = ''").fetchone()[0]

    print(f"\n=== HASIL ===")
    print(f"Updated: {updated}")
    print(f"Skipped (sudah ada alamat): {skipped_already}")
    print(f"Tidak ditemukan di DB: {len(remaining)}")
    print(f"Donatur masih tanpa alamat: {null_count}")

    if remaining:
        print(f"\n--- Tidak ditemukan ({len(remaining)}) ---")
        for nama, alamat in remaining[:30]:
            print(f"  ? {nama} -> {alamat}")
        if len(remaining) > 30:
            print(f"  ... dan {len(remaining) - 30} lagi")

    conn.close()

if __name__ == '__main__':
    main()
