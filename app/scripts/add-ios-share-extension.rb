# frozen_string_literal: true
#
# يُضيفُ هدفَ «امتدادِ المشاركة» إلى مشروعِ Xcode برمجيًّا.
#
# لماذا سكربتٌ لا تحريرٌ يدويّ: `project.pbxproj` ملفٌّ بمُعرِّفاتٍ سداسيّةٍ
# مُولَّدة، وتحريرُه بالنصِّ عرضةٌ لفسادٍ صامتٍ لا يظهرُ إلّا وقتَ البناء. ومنصّةُ
# iOS يُعيدُ Capacitor توليدَها، فأيُّ تعديلٍ يدويٍّ يضيعُ. هذا السكربتُ
# **مُتَّسِقٌ عندَ التكرار** (idempotent): يعملُ في كلِّ بناءٍ ولا يُكرّرُ الهدف.
#
#   gem install xcodeproj && ruby scripts/add-ios-share-extension.rb

require "xcodeproj"

ROOT = File.expand_path("..", __dir__)
PROJ = File.join(ROOT, "ios", "App", "App.xcodeproj")
NAME = "ShareExtension"
SRC  = File.join(ROOT, "ios", NAME)
APP_ID = "news.isnad.app"

abort("✗ لا مشروعَ في #{PROJ} — شغّلْ `npx cap add ios` أوّلًا") unless Dir.exist?(PROJ)

project = Xcodeproj::Project.open(PROJ)

if project.targets.any? { |t| t.name == NAME }
  puts "✓ #{NAME} موجودٌ سلفًا — لا تغيير"
  exit 0
end

app_target = project.targets.find { |t| t.name == "App" } || project.targets.first
abort("✗ لم أجدْ هدفَ التطبيق") unless app_target

ext = project.new_target(:app_extension, NAME, :ios, "14.0")

# مُعرِّفُ الامتدادِ يجبُ أن يكونَ ابنًا لمُعرِّفِ التطبيق، وإلّا رفضَته آبل
ext.build_configurations.each do |cfg|
  cfg.build_settings["PRODUCT_BUNDLE_IDENTIFIER"] = "#{APP_ID}.share"
  cfg.build_settings["INFOPLIST_FILE"] = "../#{NAME}/Info.plist"
  cfg.build_settings["IPHONEOS_DEPLOYMENT_TARGET"] = "14.0"
  cfg.build_settings["SWIFT_VERSION"] = "5.0"
  cfg.build_settings["TARGETED_DEVICE_FAMILY"] = "1,2"
  cfg.build_settings["CODE_SIGN_STYLE"] = "Automatic"
  cfg.build_settings["GENERATE_INFOPLIST_FILE"] = "NO"
end

group = project.main_group.find_subpath(NAME, true)
group.set_source_tree("SOURCE_ROOT")
group.set_path("../#{NAME}")

Dir[File.join(SRC, "*.swift")].sort.each do |file|
  ref = group.new_reference(File.basename(file))
  ext.add_file_references([ref])
end

# تضمينُ الامتدادِ داخلَ حزمةِ التطبيق — بدونها يُبنى ولا يُشحَن
embed = app_target.build_phases.find do |p|
  p.respond_to?(:symbol_dst_subfolder_spec) && p.symbol_dst_subfolder_spec == :plug_ins
end
embed ||= begin
  phase = project.new(Xcodeproj::Project::Object::PBXCopyFilesBuildPhase)
  phase.name = "Embed App Extensions"
  phase.symbol_dst_subfolder_spec = :plug_ins
  app_target.build_phases << phase
  phase
end
embed.add_file_reference(ext.product_reference, true)
app_target.add_dependency(ext)

project.save
puts "✓ أُضيفَ #{NAME} (#{APP_ID}.share) ورُبِطَ بالتطبيق"
