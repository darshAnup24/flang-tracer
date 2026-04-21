! C10: ASSOCIATE + SELECT TYPE
program associate_select
    implicit none
    type :: Shape
    end type Shape
    
    type, extends(Shape) :: Circle
        real :: radius
    end type Circle
    
    class(Shape), allocatable :: s
    
    allocate(Circle :: s)
    
    ! The construct below will be traced
    select type(t => s)
    type is(Circle)
        t%radius = 5.0
    end select
end program associate_select
