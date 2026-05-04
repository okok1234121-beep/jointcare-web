-- 樂齡健康動 - 資料庫結構備份
-- 適用於 MySQL 8.0+

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- 1. 使用者個人檔案 (基本資料)
-- ----------------------------
CREATE TABLE IF NOT EXISTS `User_profiles` (
  `User_id` int NOT NULL AUTO_INCREMENT,
  `Name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '顯示姓名',
  `Gender` enum('M','F') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'M',
  `Age` int DEFAULT '65',
  `Weight` int DEFAULT '60',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`User_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 2. LINE 帳號連結表 (登入憑證)
-- ----------------------------
CREATE TABLE IF NOT EXISTS `line_accounts` (
  `auth_id` int NOT NULL AUTO_INCREMENT,
  `line_user_id` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'LINE UID',
  `user_id` int NOT NULL COMMENT '對應 User_profiles',
  `display_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `picture_url` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `last_login` datetime DEFAULT NULL,
  PRIMARY KEY (`auth_id`),
  UNIQUE KEY `line_user_id` (`line_user_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `line_accounts_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `User_profiles` (`User_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 3. 好友/家屬關係表
-- ----------------------------
CREATE TABLE IF NOT EXISTS `friendships` (
  `friendship_id` int NOT NULL AUTO_INCREMENT,
  `requester_id` int NOT NULL COMMENT '發送者 User_id',
  `receiver_id` int NOT NULL COMMENT '接收者 User_id',
  `status` enum('pending','accepted') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'pending',
  `relation_type` enum('friend','family') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'friend' COMMENT '關係類型: 朋友或家屬',
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`friendship_id`),
  UNIQUE KEY `unique_friendship` (`requester_id`,`receiver_id`),
  KEY `receiver_id` (`receiver_id`),
  CONSTRAINT `friendships_ibfk_1` FOREIGN KEY (`requester_id`) REFERENCES `User_profiles` (`User_id`) ON DELETE CASCADE,
  CONSTRAINT `friendships_ibfk_2` FOREIGN KEY (`receiver_id`) REFERENCES `User_profiles` (`User_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 4. 運動紀錄表 (預留擴充)
-- ----------------------------
CREATE TABLE IF NOT EXISTS `exercise_records` (
  `record_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `game_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `score` int DEFAULT '0',
  `angle` float DEFAULT '0',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`record_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `exercise_records_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `User_profiles` (`User_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
