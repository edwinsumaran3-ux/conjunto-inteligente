#include "gateway/sequence_store.hpp"
#include <sqlite3.h>
#include <stdexcept>
namespace gateway {
SequenceStore::SequenceStore(const std::filesystem::path& path) {
    if (sqlite3_open(path.string().c_str(), &db_) != SQLITE_OK) throw std::runtime_error("No se pudo abrir sequence store");
    char* err=nullptr;
    const char* sql="PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS sequence_state(id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER NOT NULL); INSERT OR IGNORE INTO sequence_state(id,value) VALUES(1,0);";
    if (sqlite3_exec(db_,sql,nullptr,nullptr,&err)!=SQLITE_OK){std::string m=err?err:"sqlite error"; sqlite3_free(err); sqlite3_close(db_); db_=nullptr; throw std::runtime_error(m);}
}
SequenceStore::~SequenceStore(){if(db_) sqlite3_close(db_);}
std::uint64_t SequenceStore::next(){std::lock_guard lock{mtx_}; if(sqlite3_exec(db_,"BEGIN IMMEDIATE; UPDATE sequence_state SET value=value+1 WHERE id=1;",nullptr,nullptr,nullptr)!=SQLITE_OK) throw std::runtime_error("sequence begin/update failed"); sqlite3_stmt* st=nullptr; if(sqlite3_prepare_v2(db_,"SELECT value FROM sequence_state WHERE id=1;",-1,&st,nullptr)!=SQLITE_OK){sqlite3_exec(db_,"ROLLBACK;",nullptr,nullptr,nullptr); throw std::runtime_error("sequence select failed");} int rc=sqlite3_step(st); auto v=rc==SQLITE_ROW?static_cast<std::uint64_t>(sqlite3_column_int64(st,0)):0; sqlite3_finalize(st); if(rc!=SQLITE_ROW){sqlite3_exec(db_,"ROLLBACK;",nullptr,nullptr,nullptr); throw std::runtime_error("sequence read failed");} if(sqlite3_exec(db_,"COMMIT;",nullptr,nullptr,nullptr)!=SQLITE_OK){sqlite3_exec(db_,"ROLLBACK;",nullptr,nullptr,nullptr); throw std::runtime_error("sequence commit failed");} return v;}
}
